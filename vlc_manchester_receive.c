#include "vlc_manchester_receive.h"

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>

#include "xtimer.h"
#include "periph/gpio.h"
#include "mutex.h"

// PA22 GPIO/Interrupt pin, TODO: external interrupt pin needed or normal gpio pin?
#define INPUT_PIN (GPIO_PIN(0, 22))

#define DEBUG_OUT_PIN_INTERRUPT_RECV (GPIO_PIN(0,28))
#define DEBUG_OUT_PIN_ENDFLAG (GPIO_PIN(0,13))

// #define DEBUG_OUT_PIN_BITSTUFFING (GPIO_PIN(0,16))

#define TIMEOUT_WHILE_SYNCING_US 5000

// factor to avoid floating point division (which is very time consuming), can be applied before devision and afterwards at comparison
static uint32_t _precision_int_div = 10000;

// transmission specific internal values used for decoding
struct receive_context_t
{
    char *receive_buffer;                   // buffer where the received data is stored
    unsigned char received_byte;            // stores the current byte

    volatile unsigned char current_bit_count;
    volatile unsigned int byte_count;       // number of bytes received

    enum edge last_edge;
    uint32_t symbol_rate_us;                // double of switching rate
    volatile uint32_t last_symbol_time;     // last time stamp where a bit was transmitted

    // remaining_sync_edges = 2 * num_sync_symbols; must be set at initialization because num_sync_symbols is not cons
    unsigned int remaining_sync_edges;

    // time [in us] after an incoming edge is interpreted as a new signal; must be set after syncing; depending on symbol_rate
    unsigned int timeout_us;

    mutex_t receive_in_progress;            // only used by sync read

    unsigned int synchronous;               // 1 if receive is blocking

    unsigned char bit_stuffing_count;       // number of ones in row
    // unsigned char flag_received;            // 1 if flag received or waiting for the last bit of the flag

};

// used to pass a timer function to the isr and to be able to run tests
typedef unsigned int (*current_time_func)(unsigned int);
static current_time_func _get_current_time = &timer_read;

// context of the current transmission process
static struct receive_context_t _receive_context;

// configuration of the receiver, to be set initially
static struct receive_configuration_t _receive_configuration;

// metadata of transmission result
static struct receive_result_meta_t *_receive_result_meta;

static void _init_receive_context(struct receive_context_t *_receive_context) {
    _receive_context->received_byte = 0;
    _receive_context->byte_count = 0;
    _receive_context->current_bit_count = 0;
    _receive_context->last_edge = FALLING;
    _receive_context->symbol_rate_us = 0;
    _receive_context->last_symbol_time = 0;
    _receive_context->remaining_sync_edges = 0;
    _receive_context->timeout_us = 0;
    _receive_context->synchronous = 1;

    _receive_context->bit_stuffing_count = 0;

    mutex_init(&_receive_context->receive_in_progress);
}

static void _reset_manchester_receive(void) {
    _receive_context.remaining_sync_edges = 2 * _receive_configuration.num_sync_symbols;
    _receive_context.symbol_rate_us = 0;
    _receive_context.received_byte = 0;
    _receive_context.current_bit_count = 0;
    _receive_context.timeout_us = 0;
    _receive_context.byte_count = 0;
    _receive_context.bit_stuffing_count = 0;

    _receive_context.last_edge = FALLING;
}

// reset the receiver after a transmission was finished and the buffer and meta data was saved
void vlc_reset_receiver(void) {

    _reset_manchester_receive();

    // interrupt was disabled after transmission was complete --> enable again for next transmission
    gpio_irq_enable(INPUT_PIN);
}

// takes about 16us
static void _interrupt_changing_edge(void *is_receiving_lock) {

    (void) is_receiving_lock;
#ifdef DEBUG_OUT_PIN_INTERRUPT_RECV
    gpio_write(DEBUG_OUT_PIN_INTERRUPT_RECV, 1);
#endif

    // store current interrupt time as early as possible to avoid a shift in time due to the execution time of the isr
    // TODO: check for overflow
    // TODO: avoid function call
    uint32_t current_edge_time = _get_current_time(1);
    uint32_t time_diff_last_symbol = current_edge_time - _receive_context.last_symbol_time;

    // check if a new message is received
    // if timeout already calculated and greater than timeout, 
    // or if the timeout was not calculated (due to signal loss while syncing or very first signal) and the last signal was half a second in the past
    if (((_receive_context.timeout_us != 0) && (time_diff_last_symbol >= _receive_context.timeout_us)) ||
        (_receive_context.timeout_us == 0 && (time_diff_last_symbol >= TIMEOUT_WHILE_SYNCING_US))) {

        // TODO: reset is called twice after vlc_reset_receiver has been called after successful transmission
        _reset_manchester_receive();
    }

    // TODO: use other condition: buffer emtpy && received_byte = 0
    // sync bits
    if (_receive_context.remaining_sync_edges > 0) {

        // calculate the symbol rate, use average of measured sync edge times
        // if the current sync edge is not the first
        if (_receive_context.remaining_sync_edges < (2 * _receive_configuration.num_sync_symbols)) {
            // (2 * num_sync_symbols - 1) is the number of differences measured
            _receive_context.symbol_rate_us += _precision_int_div * time_diff_last_symbol / (2 * _receive_configuration.num_sync_symbols - 1);
        }

        // the last falling edge of the synchronization sets the first reference for the symbol time
        if (_receive_context.remaining_sync_edges == 1) {
            // multiply by 2 because the sync bits are half of the symbol rate
            _receive_context.symbol_rate_us *= 2;
            // should never happen
            if (_precision_int_div == 0) {
                puts("--- detected 0 division! ---");
                return;
            }
            _receive_context.symbol_rate_us /= _precision_int_div;

            // TODO: use tolerance
            // timeout should occur after the current timestamp is outside the tolerance scope
            _receive_context.timeout_us = 2 * _receive_context.symbol_rate_us;

            assert(_receive_context.symbol_rate_us > 0);
        }

        // store the last edge time in last_symbol time to calculate the symbol- and bit rate
        // and also to have a time reference for the first symbol
        _receive_context.last_symbol_time = current_edge_time;

        _receive_context.remaining_sync_edges--;
#ifdef DEBUG_OUT_PIN_INTERRUPT_RECV
        gpio_write(DEBUG_OUT_PIN_INTERRUPT_RECV, 0);
#endif
        return;
    }

    // swap RISING AND FALLING
    _receive_context.last_edge = _receive_context.last_edge ^ 1;

    // current edge is matching the symbol rate --> read bit
    // TODO: calculate "100 - " in tolerance and change to >=
    // TODO: overflow detection
    // NOTE: last_edge is now the current edge
    if (_receive_context.symbol_rate_us == 0) {
        // should never happen
        puts("--- detected 0 division! ---");
        return;
    }
    uint32_t edge_time_symbol_rate_ratio = (_precision_int_div * time_diff_last_symbol) / _receive_context.symbol_rate_us;
    if (((time_diff_last_symbol <= _receive_context.symbol_rate_us) && (100 * _precision_int_div - (edge_time_symbol_rate_ratio * 100)) <= _receive_configuration.tolerance * _precision_int_div) ||
         ((time_diff_last_symbol > _receive_context.symbol_rate_us) && ((edge_time_symbol_rate_ratio * 100) <= (100 + _receive_configuration.tolerance) * _precision_int_div))) {

        // check for stuffed 0 after 6 ones or interpret end flag 
        if (_receive_context.bit_stuffing_count >= 6) {

            if (_receive_context.bit_stuffing_count == 6 && _receive_context.last_edge == 0) // bit was stuffed
            {
                // gpio_write(DEBUG_OUT_PIN_BITSTUFFING, 1);
                // NOTE: bit_stuffing_count must not be reset on end flag because the next bit
                // is not part of the payload too
                _receive_context.bit_stuffing_count = 0;
            }
            // check if bit signals start of a flag or is the last bit of the flag
            // flags are starting with 7 ones
            // _receive_context.current_bit_count increased after bit stuffing check
            else {
                // check if bit signals start of a flag (penultimate bit)
                // current edge must be 1 at this check, otherwise the bitstuffing encoding is wrong
                if (_receive_context.bit_stuffing_count == 6 && _receive_context.last_edge == 1) {

                    // next bit needed to interpret flag
                    _receive_context.bit_stuffing_count++;

                }
                // check if the bit is the last
                else if (_receive_context.bit_stuffing_count == 7) {

                    // mark message as complete
                    _receive_context.current_bit_count = 0;

                    // check if end of transmission (flag = 11111110)
                    if (_receive_context.last_edge == 0) {
#ifdef DEBUG_OUT_PIN_ENDFLAG
                        gpio_write(DEBUG_OUT_PIN_ENDFLAG, 1);
#endif
                        gpio_irq_disable(INPUT_PIN);
                        _receive_result_meta->num_bytes_read = _receive_context.byte_count;

                        _receive_result_meta->data_rate = 1000000 / _receive_context.symbol_rate_us;
                        _receive_configuration.netdev->event_callback(_receive_configuration.netdev, NETDEV_EVENT_ISR);
#ifdef DEBUG_OUT_PIN_ENDFLAG
                        gpio_write(DEBUG_OUT_PIN_ENDFLAG, 0);
#endif
                    }
                    else    // flag = 11111111
                    {
                        // NOTE: can be used for other flags
                    }
                }
                else
                {
                    // TODO: remove, only good for debugging
                    printf("ERROR: wrong encoding (bit stuffing)\n");
                }
            }

            _receive_context.last_symbol_time = current_edge_time;
#ifdef DEBUG_OUT_PIN_INTERRUPT_RECV
            gpio_write(DEBUG_OUT_PIN_INTERRUPT_RECV, 0);
#endif
            // gpio_write(DEBUG_OUT_PIN_BITSTUFFING, 0);
            
            // bit was stuffed or end flag => skip
            return;
        }

        // update bit stuffing count
        // NOTE: bit stuffing count will be reset if byte complete
        if (_receive_context.last_edge == 1) {
            _receive_context.bit_stuffing_count++;
        }
        else
        {
            _receive_context.bit_stuffing_count = 0;
        }

        // set the current bit for the currently receiving byte
        // last_edge is the current edge
        // TODO: change encoding to Least Significant Bit First so that (7 -) is no more necessary, or change counting (start by 7 and decrement?)
        _receive_context.received_byte = _receive_context.received_byte | (_receive_context.last_edge << (7 - _receive_context.current_bit_count));

        // last bit of byte was received 
        if (_receive_context.current_bit_count++ >= 7) {

            if (_receive_context.byte_count < _receive_configuration.buffer_size) {
                _receive_context.receive_buffer[_receive_context.byte_count] = _receive_context.received_byte;
            }
            else {
                puts("Receiver: BUFFER OVERFLOW! -> reset");
                _reset_manchester_receive();
                return;
            }

            _receive_context.byte_count ++;
            _receive_context.current_bit_count = 0;
            _receive_context.bit_stuffing_count = 0;
            _receive_context.received_byte = 0;
        }

        _receive_context.last_symbol_time = current_edge_time;
    }
#ifdef DEBUG_OUT_PIN_INTERRUPT_RECV
    gpio_write(DEBUG_OUT_PIN_INTERRUPT_RECV, 0);
#endif
}

// bool _is_receive_complete(void) {
//     unsigned irq_state = irq_disable();
//     _receive_context.
//     irq_restore(irq_state);

//     return  
// }

void vlc_init_receiver(void *buffer, struct receive_configuration_t config, struct receive_result_meta_t *result_meta) {

#ifdef DEBUG_OUT_PIN_INTERRUPT_RECV
    gpio_init(DEBUG_OUT_PIN_INTERRUPT_RECV, GPIO_OUT);
#endif
#ifdef DEBUG_OUT_PIN_ENDFLAG
    gpio_init(DEBUG_OUT_PIN_ENDFLAG, GPIO_OUT);
#endif
    // gpio_init(DEBUG_OUT_PIN_BITSTUFFING, GPIO_OUT);

    _receive_context.receive_buffer = buffer;

    _receive_result_meta = result_meta;

    _init_receive_context(&_receive_context);

    // TODO: just assign
    _receive_configuration.tolerance = config.tolerance;
    _receive_configuration.num_sync_symbols = config.num_sync_symbols;
    _receive_configuration.netdev = config.netdev;
    _receive_configuration.buffer_size = config.buffer_size;

    _receive_context.remaining_sync_edges = 2 * _receive_configuration.num_sync_symbols;
    _receive_context.synchronous = config.synchronous;

    // TODO: assert num_sync:symbols > 0

    printf("Setup manchester decoder: tolerance = %i%%; num_sync_symbols = %i; ", _receive_configuration.tolerance, _receive_configuration.num_sync_symbols);
    printf("read mode: %s\n", (_receive_context.synchronous) == 0 ? "asynchronous" : "synchronous");

    // TODO: cover case if interrupt occurres after init and before disable
    gpio_init_int(INPUT_PIN, GPIO_IN, GPIO_BOTH, _interrupt_changing_edge, (void *) GPIO_BOTH);

    if (config.synchronous >= 1) {
        gpio_irq_disable(INPUT_PIN);
    }

    _reset_manchester_receive();
}

static void _manchester_read_sync(struct receive_result_meta_t *result_meta) {
    
    gpio_irq_enable(INPUT_PIN);

    // wait until a transmission is started and sync ready so that timeout_us is calculated
    // TODO: use transmission state SYNC_READY (need to know the timeout)
    // TODO: implement timeout until function returns without data
    // TODO: implement sync timeout in case transmission breaks while syncing
    while (_receive_context.current_bit_count == 0 && _receive_context.byte_count == 0) {
        xtimer_mutex_lock_timeout(&_receive_context.receive_in_progress, 1000);
    }

    // unlock mutex so that the first timeout mutex lock returns immediately
    mutex_unlock(&_receive_context.receive_in_progress);

    unsigned int time_div = 0;
    // TODO: timeout should depend on the tolerance
    // wait until message is completely received (timeout occurred)
    do {
        xtimer_mutex_lock_timeout(&_receive_context.receive_in_progress, _receive_context.timeout_us);

        // gpio_irq_enable would discard all interrupts since disable
        unsigned irq_state = irq_disable();
        time_div = timer_read(1) - _receive_context.last_symbol_time;
        irq_restore(irq_state);

    } while (time_div < _receive_context.timeout_us);

    gpio_irq_disable(INPUT_PIN);

    result_meta->num_bytes_read = _receive_context.byte_count;
    if (_receive_context.current_bit_count == 0) {
        result_meta->state = COMPLETE;
    }
    else
    {
        result_meta->state = INCOMPLETE;
    }

    result_meta->data_rate = 1000000 / _receive_context.symbol_rate_us;
    
    _reset_manchester_receive();
}

static void _manchester_read_async(struct receive_result_meta_t *result_meta) {

    (void) result_meta;

    // unsigned irq_state = irq_disable();
    // irq_restore(irq_state);

    // return _receive_context.receive_buffer;

}

void manchester_read(struct receive_result_meta_t *result_meta) {

    if (_receive_context.synchronous == 1)
    {
        _manchester_read_sync(result_meta);
    }
    else
    {
        _manchester_read_async(result_meta);
    }
}

/**
 * 
 * TEST CODE
 * 
**/

// test helpers

static void _setup_test(void) {
    _receive_configuration.tolerance = 30;
    _receive_configuration.num_sync_symbols = 4;
    _receive_configuration.synchronous = 0;
    _init_receive_context(&_receive_context);
}

static unsigned int _timer_test_value = 0; 
static unsigned int _timer_test_function(unsigned int x) {
    (void) x;
    return _timer_test_value;
}

static void _assert_equal_num(int a, int b, char *name_a, char *name_b) {
    if (a != b) {
        printf("[ERROR] %s != %s (%i != %i)\n", name_a, name_b, a, b);
        exit(1);
    }
}

// NOTE: currently no buffer comparison
static void _assert_receive_context_equal(struct receive_context_t *receive_context1, struct receive_context_t *receive_context2) {

    // TODO: assert receive buffer
    _assert_equal_num(receive_context1->received_byte, receive_context2->received_byte,
                "receive_context1->received_byte", "receive_context2->received_byte");

    _assert_equal_num(receive_context1->current_bit_count, receive_context2->current_bit_count,
                "receive_context1->current_bit_count", "receive_context2->current_bit_count");
    
    _assert_equal_num(receive_context1->byte_count, receive_context2->byte_count,
                "receive_context1->byte_count", "receive_context2->byte_count");
    
    _assert_equal_num(receive_context1->last_edge, receive_context2->last_edge,
                "receive_context1->last_edge", "receive_context2->last_edge");

    _assert_equal_num(receive_context1->symbol_rate_us, receive_context2->symbol_rate_us,
                "receive_context1->symbol_rate_us", "receive_context2->symbol_rate_us");
    
    _assert_equal_num(receive_context1->last_symbol_time, receive_context2->last_symbol_time,
                "receive_context1->last_symbol_time", "receive_context2->last_symbol_time");

    _assert_equal_num(receive_context1->remaining_sync_edges, receive_context2->remaining_sync_edges,
                "receive_context1->remaining_sync_edges", "receive_context2->remaining_sync_edges");
    
    _assert_equal_num(receive_context1->timeout_us, receive_context2->timeout_us,
                "receive_context1->timeout_us", "receive_context2->timeout_us");
    
    _assert_equal_num(receive_context1->synchronous, receive_context2->synchronous,
                "receive_context1->synchronous", "receive_context2->synchronous");
    
    _assert_equal_num(receive_context1->bit_stuffing_count, receive_context2->bit_stuffing_count,
                "receive_context1->bit_stuffing_count", "receive_context2->bit_stuffing_count");
}

// only asserts that values has been reset 
// void assert_reset_done(struct receive_context_t *_receive_context) {

//     // TODO: assert receive buffer
//     _assert_equal_num(_receive_context->received_byte, 0,
//                 "_receive_context->received_byte", "0");

//     _assert_equal_num(_receive_context->current_bit_count, 0,
//                 "_receive_context->current_bit_count", "0");
    
//     _assert_equal_num(_receive_context->byte_count, 0,
//                 "_receive_context->byte_count", "0");
    
//     _assert_equal_num(_receive_context->last_edge, 0,
//                 "_receive_context->last_edge", "0");

//     _assert_equal_num(_receive_context->symbol_rate_us, 0,
//                 "_receive_context->symbol_rate_us", "0");

//     // last symbol time unchanged
    
//     _assert_equal_num(_receive_context->remaining_sync_edges, 2 * _receive_configuration.num_sync_symbols,
//                 "_receive_context->remaining_sync_edges", "2 * _receive_configuration.num_sync_symbols");
    
//     _assert_equal_num(_receive_context->timeout_us, 0,
//                 "_receive_context->timeout_us", "0");

//     // synchronous unchanged

//     _assert_equal_num(_receive_context->bit_stuffing_count, 0,
//                 "_receive_context->bit_stuffing_count", "0");
// }

// test functions

// test if vlc_reset_receiver resets the context
static void _test_reset(void) {

    _receive_context.received_byte = 0b10101010;
    _receive_context.current_bit_count = 42;
    _receive_context.byte_count = 3;
    _receive_context.last_edge = RISING;
    _receive_context.symbol_rate_us = 1500;
    _receive_context.last_symbol_time = 1234567;
    _receive_context.remaining_sync_edges = 0;
    _receive_context.timeout_us = 5000;
    _receive_context.synchronous = 1;
    _receive_context.bit_stuffing_count = 4;

    struct receive_context_t target_context;
    target_context.received_byte = 0;
    target_context.current_bit_count = 0;
    target_context.byte_count = 0;
    target_context.last_edge = FALLING;
    target_context.symbol_rate_us = 0;

    // could also be changed, but then would reset after a timeout always executed twice 
    // (vlc_reset_receiver has been called after successful transmission and in isr timeout handling)
    target_context.last_symbol_time = 1234567;

    target_context.remaining_sync_edges = _receive_configuration.num_sync_symbols * 2;
    target_context.timeout_us = 0;
    target_context.synchronous = 1;
    target_context.bit_stuffing_count = 0;

    vlc_reset_receiver();

    _assert_receive_context_equal(&_receive_context, &target_context);
}

// test that the timeout occurres while syncing (the timeout is still not set)
// and resets the context and processes the first sync signal
static void _test_timeout_while_syncing(void) {

    // trigger timeout
    _timer_test_value = 100000 + TIMEOUT_WHILE_SYNCING_US;
    _receive_context.last_symbol_time = 100000;

    // timeout while syncing
    _receive_context.remaining_sync_edges = 3;

    // target context should be reset and first sync iteration complete
    struct receive_context_t target_context;
    _init_receive_context(&target_context);
    target_context.last_symbol_time = _timer_test_value;
    target_context.remaining_sync_edges = 2 * _receive_configuration.num_sync_symbols - 1;

    _interrupt_changing_edge(NULL);

    _assert_receive_context_equal(&_receive_context, &target_context);
}

// test second sync edge
static void _test_second_sync_edge(void) {

    // no timeout
    _timer_test_value = 100100 + TIMEOUT_WHILE_SYNCING_US - 100;
    _receive_context.last_symbol_time = 100100;
    unsigned int time_diff = _timer_test_value - _receive_context.last_symbol_time;

    // first sync edge already processed
    _receive_context.remaining_sync_edges = 2 * _receive_configuration.num_sync_symbols - 1;

    struct receive_context_t target_context = _receive_context;
    // target context should stay equal except:
    target_context.last_symbol_time = _timer_test_value;
    target_context.remaining_sync_edges = 2 * _receive_configuration.num_sync_symbols - 2;
    target_context.symbol_rate_us = time_diff / (2 * _receive_configuration.num_sync_symbols - 1) * _precision_int_div;
    // NOTE: last edge is not update while syncing because it is not needed there

    _interrupt_changing_edge(NULL);

    _assert_receive_context_equal(&_receive_context, &target_context);
}

// test last sync edge
static void _test_last_sync_edge(void) {

    // no timeout
    _timer_test_value = 100100 + TIMEOUT_WHILE_SYNCING_US - 100;
    _receive_context.last_symbol_time = 100100;
    unsigned int time_diff = _timer_test_value - _receive_context.last_symbol_time;

    // last sync edge
    _receive_context.remaining_sync_edges = 1;

    // all past sync edges with the same symbol rate, time_diff as average value
    _receive_context.symbol_rate_us = (2 * _receive_configuration.num_sync_symbols - 2) * (_precision_int_div * time_diff / (2 * _receive_configuration.num_sync_symbols - 1));

    struct receive_context_t target_context = _receive_context;
    // target context should stay equal except:
    target_context.last_symbol_time = _timer_test_value;
    target_context.remaining_sync_edges = 0;
    target_context.symbol_rate_us = 2 * time_diff;  // time_diff as average value, sync bits half of symbol rate
    target_context.timeout_us = 2 * target_context.symbol_rate_us;
    // NOTE: last edge is not update while syncing because it is not needed there

    _interrupt_changing_edge(NULL);

    _assert_receive_context_equal(&_receive_context, &target_context);
}

// public function
void vlc_receiver_run_unit_tests(void) {

    typedef void(*test_function)(void);
    struct test
    {
        test_function func;
        char *name;
    };
    
    const unsigned int num_tests = 4;
    struct test tests[] = {
    // NOTE: DO NOT FORGET TO ADJUST NUM OF TESTS
        {&_test_reset, "_test_reset"},
        {&_test_timeout_while_syncing, "_test_timeout_while_syncing"},
        {&_test_second_sync_edge, "_test_second_sync_edge"},
        {&_test_last_sync_edge, "_test_last_sync_edge"},
    };

    // use test timer function for the current timestamp in the isr
    _get_current_time = &_timer_test_function;

    for (size_t i = 0; i < num_tests; i++)
    {
        _setup_test();
        printf("[START] %s\n", tests[i].name);
        tests[i].func();
        printf("[SUCCESS] %s\n", tests[i].name);
    }

    _reset_manchester_receive();
    _get_current_time = &timer_read;

    printf("Unit tests successful\n");
}
