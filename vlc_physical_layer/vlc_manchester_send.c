#include "vlc_manchester_send.h"

#include <stdio.h>

#include "periph/timer.h"
#include "periph/gpio.h"
#include "mutex.h"
#include "xtimer.h"

#define ENABLE_DEBUG 0
#include "debug.h"

#define LED_PIN 15
// #define DEBUG_OUT_PIN_INTERRUPT (GPIO_PIN(0,16))
// #define DEBUG_OUT_PIN_SEND_FINISHED (GPIO_PIN(0,14))

#define TIMER_NUM 0    // timer which is used for sending

static char _end_flag = 0b11111110;             // flag which signals end of transmission

// transmission specific internal values used for decoding
struct send_context_t
{
    char *send_buffer;                  // buffer of the data to send
    int send_buffer_length;             // length of send buffer
    int send_buffer_position;           // counts current bit

    char is_data_edge;                  // 1 if the current edge encodes data
    char current_bit;                   // the current bit in process
    char remaining_sync_signals;        // number of remaining sync edges
    // TODO: use edge struct
    char last_sync_signal;              // state of the last sync edge (RISING FALLING)
    char payload_transmitted;           // 1 if payload transmitted and _end_flag can be send

    unsigned char bit_stuffing_count;   // number of ones in row
    mutex_t is_sending_lock;            // mutex which is locked until transmission complete
};

// send context
static struct send_context_t _send_context;

static void _init_send_context(struct send_context_t *_send_context) {
    _send_context->send_buffer_length = 0;
    _send_context->send_buffer_position = 0;

    _send_context->is_data_edge = 0;
    _send_context->current_bit = 0;
    _send_context->remaining_sync_signals = 0;
    // TODO: use edge struct
    _send_context->last_sync_signal = 1;
    _send_context->payload_transmitted = 0;

    // mutex_init(&_send_context->is_sending_lock);
}

// takes mutex which gets unlocked after send is finished
static int _setup_vlc_manchester_send(int bitrate) {
    int timer_interval_us = (int) (1.0 / ((double) bitrate) * 1000000.0 / 2.0);

    gpio_write(GPIO_PIN(0,LED_PIN), 0);

    if (bitrate > (1000000.0 / 2.0)) {
        printf("Bitrate too high for timer clocked at 1MHz!\n");
        return 1;
    }

    // 40 kbit/s seems to be the upper bound 
    if (bitrate > 40000)
    {
        printf("WARNING: Bitrates above 40kbit/s seems to have no effect!\n");
    }

    mutex_lock(&_send_context.is_sending_lock);

    DEBUG("vlc send: Start periodic timer each %dus\n", timer_interval_us);
    timer_start(TIMER_DEV(TIMER_NUM));
    int err = timer_set_periodic(TIMER_DEV(TIMER_NUM), 0, timer_interval_us, TIM_FLAG_RESET_ON_MATCH);
    if (err == -1)
    {
        printf("Error during setup of periodic timer\n");
        return 1;
    }
    DEBUG("vlc send: setup ready\n");

    return 0;
}

static void _reset_send_context(void) {
    _send_context.send_buffer_position = 0;
    
    _send_context.send_buffer_length = 0;
    _send_context.is_data_edge = 0;
    _send_context.current_bit = 0;
    _send_context.remaining_sync_signals = 0;
    _send_context.last_sync_signal = 1;
    _send_context.payload_transmitted = 0;
}

static void _send_callback(void *_unused_1, int _unused_2) {
    (void) _unused_1;
    (void) _unused_2;

#ifdef DEBUG_OUT_PIN_INTERRUPT
    gpio_write(DEBUG_OUT_PIN_INTERRUPT, 1);
#endif

    // send buffer contains chars, 8 bit
    // transmission finished
    if (_send_context.send_buffer_position >= (8 * _send_context.send_buffer_length)) {

        // if payload transmitted is 0, this is the first call after the payload was transmitted
        if (_send_context.payload_transmitted == 0)
        {
            // setup context to just send the _end_flag and to afterwards reach the following else block
            _send_context.send_buffer_position = 0;
            _send_context.send_buffer_length = 1;

            _send_context.send_buffer = &_end_flag;

            _send_context.payload_transmitted = 1;
        }
        else    // payload and _end_flag transmitted
        {
#ifdef DEBUG_OUT_PIN_SEND_FINISHED
            gpio_write(DEBUG_OUT_PIN_SEND_FINISHED, 1);
#endif
            timer_stop(TIMER_DEV(TIMER_NUM));
            mutex_unlock(&_send_context.is_sending_lock);
            gpio_write(GPIO_PIN(0,LED_PIN), 0);
#ifdef DEBUG_OUT_PIN_INTERRUPT
            gpio_write(DEBUG_OUT_PIN_INTERRUPT, 0);
#endif
#ifdef DEBUG_OUT_PIN_SEND_FINISHED
            gpio_write(DEBUG_OUT_PIN_SEND_FINISHED, 0);
#endif
            return;
        }
    }

    // syncing
    if (_send_context.remaining_sync_signals > 0) {
        gpio_write(GPIO_PIN(0,LED_PIN), _send_context.last_sync_signal);

        // xor 1 to swap next signal
        _send_context.last_sync_signal = _send_context.last_sync_signal ^ 1;

        _send_context.remaining_sync_signals --;
#ifdef DEBUG_OUT_PIN_INTERRUPT
        gpio_write(DEBUG_OUT_PIN_INTERRUPT, 0);
#endif
        return;
    }

    // if it is not the data edge the current bit to send needs be known to adjust the output level
    if (_send_context.is_data_edge == 0)
    {
        // gpio_write(DEBUG_OUT_PIN_BITSTUFFING, 0);

        // get the current bit directly from the string message to send
        int string_index = _send_context.send_buffer_position / 8;
        int char_index = _send_context.send_buffer_position % 8;

        char c = _send_context.send_buffer[string_index];

        _send_context.current_bit = (c >> (7 - char_index)) & 1;

        if (char_index == 0) {
            _send_context.bit_stuffing_count = 0;
        }
        // check if bit stuffing needed, 6 ones in a row
        if (_send_context.bit_stuffing_count >= 6)
        {
            // gpio_write(DEBUG_OUT_PIN_BITSTUFFING, 1);
            // stuff 0
            _send_context.current_bit = 0;
        }
        // update bit stuffing count
        if ((_send_context.current_bit == 0 && _send_context.bit_stuffing_count < 6) || _send_context.payload_transmitted == 1) {
            _send_context.bit_stuffing_count = 0;
        }
        else // _send_context.current_bit == 1 || _send_context.bit_stuffing_count >= 6
        {
            _send_context.bit_stuffing_count ++;
        }

        // set output to LOW if current bit is 1 to create a rising edge with the next function call
        // set output to HIGH if current bit is 0 to create a falling edge with the next function call
        // xor 1 to swap the bit
        gpio_write(GPIO_PIN(0,LED_PIN), _send_context.current_bit ^ 1);

        // next function call sends edge which encodes the data
        _send_context.is_data_edge = 1;
    } 
    else // _send_context.is_data_edge = 1
    {
        gpio_write(GPIO_PIN(0,LED_PIN), _send_context.current_bit);

        // check if bit was stuffed
        // only increase buffer position if no bit was stuffed so that no bit get lost
        if (_send_context.bit_stuffing_count >= 7) {
            _send_context.bit_stuffing_count = 0;
        }
        else   // no bit was stuffed
        {
            _send_context.send_buffer_position ++;
        }

        _send_context.is_data_edge = 0;
    }
#ifdef DEBUG_OUT_PIN_INTERRUPT
    gpio_write(DEBUG_OUT_PIN_INTERRUPT, 0);
#endif
}

// length of message required
int vlc_manchester_send(void *message, int length, int bitrate, int num_sync_symbols) {

    _send_context.send_buffer = message;
    _send_context.send_buffer_length = length;
    _send_context.remaining_sync_signals = 2 * num_sync_symbols;

    // start send timer, unlocks _send_context.is_sending_lock when finished
    int err = _setup_vlc_manchester_send(bitrate);
    if (err > 0) {
        puts("Error during sender initialization!\n");
        return 1;
    }

    DEBUG("vlc send: waiting for send complete\n");

    // wait for the transmission to finish

    mutex_lock(&_send_context.is_sending_lock);
    // unsigned int expected_transmission_time = (length*8*1000000)/bitrate;
    // int timeout = xtimer_mutex_lock_timeout(&_send_context.is_sending_lock, 5 * expected_transmission_time);
    // if (timeout == -1) {
    //     DEBUG("vlc send: timeout\n");
    //     timer_stop(TIMER_DEV(TIMER_NUM));
    //     mutex_unlock(&_send_context.is_sending_lock);
    //     gpio_write(GPIO_PIN(0,LED_PIN), 0);
    //     _reset_send_context();
    //     return 1;
    // }
    DEBUG("vlc send: send complete\n");

    _reset_send_context();

    // mutex must be unlocked before the next call of _setup_vlc_manchester_send can lock it again
    mutex_unlock(&_send_context.is_sending_lock);

    DEBUG("vlc send: Transmission finished!\n");

    return 0;
}

int vlc_mancheser_init(void) {

    _init_send_context(&_send_context);

    // timer setup
    int clock_rate = 1 * 1000 * 1000;
    DEBUG("Setup timer with clock rate of %dMHz\n", clock_rate / 1000000);
    int err = timer_init(TIMER_DEV(TIMER_NUM), clock_rate, _send_callback, NULL);
    if (err == -1)
    {
        printf("Error during timer init: speed not applicable or unknown device given\n");
        return 1;
    }

    // gpio setup
#ifdef DEBUG_OUT_PIN_INTERRUPT
    if (gpio_init(DEBUG_OUT_PIN_INTERRUPT, GPIO_OUT) < 0) {
        puts("vlc init send: gpio init returns an error");
        return 1;
    }
#endif

#ifdef DEBUG_OUT_PIN_SEND_FINISHED
    if (gpio_init(DEBUG_OUT_PIN_SEND_FINISHED, GPIO_OUT) < 0) {
        puts("vlc init send: gpio init returns an error");
        return 1;
    }
#endif

    if (gpio_init(GPIO_PIN(0,LED_PIN), GPIO_OUT) < 0) {
        puts("vlc init send: gpio init returns an error");
        return 1;
    }

    return 0;
}
