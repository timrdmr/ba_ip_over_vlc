// extended gnrc_networking example

#include <stdio.h>
#include <stdlib.h>
#include <malloc.h>
#include "assert.h"

#include "checksum/crc8.h"

#include "shell.h"
#include "msg.h"
#include "vlc_netif.h"
#include "random.h"
#include "net/sock/udp.h"
#include "net/sock/util.h"

#include "xtimer.h"

#include "periph/timer.h"

// #define DEBUG_OUT_APP_SEND (GPIO_PIN(0,13))
#ifdef DEBUG_OUT_APP_SEND
#include "periph/gpio.h"
#endif

#define MAIN_QUEUE_SIZE     (8)
static msg_t _main_msg_queue[MAIN_QUEUE_SIZE];

#define BUFFER_SIZE 2048
// receive buffer
static u_int8_t _buffer[BUFFER_SIZE];

// payload send if not random, to check if send and received bytes are equal
static u_int8_t _test_payload[BUFFER_SIZE];

static char _measurement_package_marker = 'M';

int udp_latency_client(unsigned int runtime_us, unsigned int payload_size, unsigned int interval, unsigned int random) {

    sock_udp_ep_t local = SOCK_IPV6_EP_ANY;
    local.port = 1234;

    sock_udp_ep_t remote = { .family = AF_INET6 };
    // TODO: using this call, the udp package does not reach link layer, wrong function usage?
    // if (sock_udp_str2ep(&remote, "[fe80::6cd9:17ff:fe7d:d488]:1337") < 0) {
        // puts("Error: unable to parse destination address");
        // return 1;
    // }
    remote.port = 1337;
    // measurement independent from node
    ipv6_addr_set_all_nodes_multicast((ipv6_addr_t *)&remote.addr.ipv6,
                                  IPV6_ADDR_MCAST_SCP_LINK_LOCAL);

    sock_udp_t socket;
    if (sock_udp_create(&socket, &local, NULL, 0) < 0) {
        puts("Creating socket failed!");
        return 1;
    }

    u_int8_t *payload_buffer = malloc(payload_size);;
    if (payload_buffer == NULL) {
        printf("Memory allocation failed!\n");
        return 1;
    }
    if (!random) {
        memcpy(payload_buffer, _test_payload, payload_size);
    }

    unsigned long int i = 0;
    unsigned int start_time = timer_read(1);
    while (timer_read(1) - start_time <= runtime_us)
    {

#ifdef DEBUG_OUT_APP_SEND
        gpio_write(DEBUG_OUT_APP_SEND, 1);
#endif
        if (random) {
            // create random payload
            random_bytes(payload_buffer, payload_size);
        }

        // encode package number in last 4 bytes and marker for measurement package before
        // to avoid link layer output from other data send which are not part of the measurement
        memcpy(payload_buffer + payload_size - (sizeof(unsigned long int) + 1), &_measurement_package_marker, sizeof(unsigned long int));
        memcpy(payload_buffer + payload_size - (sizeof(unsigned long int)), &i, sizeof(unsigned long int));

        // send udp package marker
        // unsigned irq_state = irq_disable();
        printf("su %li\n", i);
        // irq_restore(irq_state);

        if (sock_udp_send(&socket, payload_buffer, payload_size, &remote) < 0) {
            puts("UDP send error");
        }

#ifdef DEBUG_OUT_APP_SEND
        gpio_write(DEBUG_OUT_APP_SEND, 0);
#endif

        // do not use periodic timer -> do not want to call send in interrupt context
        xtimer_usleep(interval);

        i ++;
    }

    free(payload_buffer);
    sock_udp_close(&socket);
    printf("fu\n");

    return 0;
}

int udp_latency_client_cmd(int argc, char **argv) {

    if (argc < 5) {
        printf("Not enough arguments! <runtime [us]> <payload size> <interval [us]> <random [0/1]>\n");
        return 1;
    }

    unsigned int runtime_us = atoi(argv[1]);
    // size in bytes
    unsigned int payload_size = atoi(argv[2]);
    unsigned int interval = atoi(argv[3]);
    unsigned int random = atoi(argv[4]);

    if (payload_size > BUFFER_SIZE) {
        puts("Receiver buffer size too small");
        return 1;
    }

    if (payload_size < sizeof(unsigned long int)) {
        puts("payload size too small - not enough bytes to encode package number");
        return 1;
    }

    if (!(random == 0 || random == 1)) {
        puts("argument random must be 0 or 1");
        return 1;
    }
    
    return udp_latency_client(runtime_us, payload_size, interval, random);
}

int udp_latency_server_cmd(int argc, char **argv) {

    unsigned int timeout = 10 * 1000000;
    if (argc < 4) {
        printf("Not enough arguments! <timeout [us]> <payload size> <random [0/1]>\n");
        return 1;
    }

    timeout = atoi(argv[1]);
    unsigned int payload_size = atoi(argv[2]);
    unsigned int random = atoi(argv[3]);

    sock_udp_ep_t local = SOCK_IPV6_EP_ANY;
    local.port = 1337;

    sock_udp_t socket;
    if (sock_udp_create(&socket, &local, NULL, 0) < 0) {
        puts("Creating socket failed!");
        return 1;
    }

    puts("rr");
    while (1)
    {
        sock_udp_ep_t remote;
        int bytes_received;

        bytes_received = sock_udp_recv(&socket, _buffer, sizeof(_buffer), timeout, &remote);
        if (bytes_received >= 0) {
            unsigned long int pkt_num;
            memcpy(&pkt_num, _buffer + bytes_received - sizeof(unsigned long int), sizeof(unsigned long int));

            if ((unsigned int) bytes_received != payload_size) {
                puts("du");
                continue;
            }
            // -5 to ignore package measurement marker and number added by the receiver
            if ((!random) && (memcmp(_buffer, _test_payload, bytes_received - 5) != 0)) {
                // payload not equal
                puts("du");
                continue;
            }

            // received udp package marker
            // unsigned irq_state = irq_disable();
            printf("ru %li\n", pkt_num);
            // irq_restore(irq_state);
        }
        else if (bytes_received == -ETIMEDOUT) {
            puts("Timeout");
            break;
        }
    }

    sock_udp_close(&socket);

    return 0;
}

// int udp_throughput_client_cmd(int argc, char **argv) {

    

//     return 0;
// }

static const shell_command_t shell_commands[] = {
    { "udp_latency_client", "<runtime_us> <payload size> <interval_us> <random [0/1]>- Latency measurement client", udp_latency_client_cmd},
    { "udp_latency_server", "<timeout_us> <payload size> <random [0/1]> - Latency measurement server", udp_latency_server_cmd},
    { NULL, NULL, NULL }
};

int main(void)
{

/*
    // CRC test
    unsigned char test_data[] = "Blablablabaasfabfigigigaidgaisbdg";
    // -1 for \0
    uint8_t checksum = crc8(test_data, sizeof(test_data) - 1, 0xAB, 0xCD);
    printf("Checksum: %i\n", checksum);
 
    return 0;
*/

#ifdef DEBUG_OUT_APP_SEND
    gpio_init(DEBUG_OUT_APP_SEND, GPIO_OUT);
#endif

    // fill test payload in case random payload is not used
    // test message with increasing bytes
    for (size_t i = 0; i < BUFFER_SIZE; i++)
    {
        _test_payload[i] = i % 256;
    }

    vlc_netif_init();

    /* we need a message queue for the thread running the shell in order to
     * receive potentially fast incoming networking packets */
    msg_init_queue(_main_msg_queue, MAIN_QUEUE_SIZE);
    puts("RIOT network stack example application");

    // init random
    random_init(123456789);

    puts("Before assert");
    assert(1 == 1);
    assert(1 == 0);
    assert(0);
    puts("After assert");

    /* start shell */
    puts("All up, running the shell now");
    char line_buf[SHELL_DEFAULT_BUFSIZE];
    shell_run(shell_commands, line_buf, SHELL_DEFAULT_BUFSIZE);

    /* should be never reached */
    return 0;
}
