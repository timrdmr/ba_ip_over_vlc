#include "vlc_netif.h"

#include <limits.h>
#include <errno.h>

#include "assert.h"
#include "thread.h"
#include "thread_flags.h"
#include "luid.h"
#include "checksum/crc8.h"

#include "net/gnrc/netif.h"
#include "net/gnrc/netif/hdr.h"
#include "net/gnrc/netreg.h"
#include "net/gnrc/pktbuf.h"
#include "net/gnrc/nettype.h"

#include "vlc_manchester_send.h"
#include "vlc_manchester_receive.h"

#define ENABLE_DEBUG            0
#include "debug.h"

#ifdef MODULE_GNRC_SIXLOWPAN
#define NETTYPE                 GNRC_NETTYPE_SIXLOWPAN
#elif defined(MODULE_GNRC_IPV6)
#define NETTYPE                 GNRC_NETTYPE_IPV6
#else
#define NETTYPE                 GNRC_NETTYPE_UNDEF
#endif

#define DATARATE_BITS_PER_SECOND 35000

// #define DEBUG_OUT_PIN_SEND_LINK (GPIO_PIN(0,28))
#ifdef DEBUG_OUT_PIN_SEND_LINK
#include "periph/gpio.h"
#endif

#define DEBUG_OUT_PIN_RECV_LINK (GPIO_PIN(0,14))
#ifdef DEBUG_OUT_PIN_RECV_LINK
#include "periph/gpio.h"
#endif


/* thread flag used for signaling transmit readiness */
#define FLAG_TX_UNSTALLED       (1u << 13)
#define FLAG_TX_NOTCONN         (1u << 12)
#define FLAG_ALL                (FLAG_TX_UNSTALLED | FLAG_TX_NOTCONN)

/* allocate a stack for the netif device */
static char _stack[THREAD_STACKSIZE_DEFAULT];
static thread_t *_netif_thread;

/* keep the actual device state */
static gnrc_netif_t _netif;
static gnrc_nettype_t _nettype = NETTYPE;

// vlc specific
#define VLC_CRC_SIZE            (1U)
#define VLC_CRC_POLYNOM         (0xAB)
#define VLC_CRC_INIT            (0xCD)

#define VLC_RECEIVER_TOLERANCE 30

#define VLC_ADDR_LEN            (6U)        /**< link layer address length */
#define MTU_SIZE                (1280U)  // maximum transport unit size
#define VLC_BUFFER_SIZE         MTU_SIZE + (2 * VLC_ADDR_LEN) + VLC_CRC_SIZE

static struct receive_configuration_t _dev_receive_conf;

static char _receive_buffer[VLC_BUFFER_SIZE];
static struct receive_result_meta_t _receive_meta_data;
static eui48_t _vlc_mac_address;
static char _send_buffer[VLC_BUFFER_SIZE];

// TODO: pass input pin to driver, duplicated code...
#ifndef INPUT_PIN
#define INPUT_PIN (GPIO_PIN(0, 22))
#endif

static void _netif_init(gnrc_netif_t *netif)
{
    DEBUG_POS("ENTER _netif_init\n");
    (void)netif;

    // store hardware address
    luid_get_eui48(&_vlc_mac_address);
    // printf("Hardware address: %02x:%02x:%02x:%02x:%02x:%02x\n", 
    //     _vlc_mac_address.uint8[0],
    //     _vlc_mac_address.uint8[1],
    //     _vlc_mac_address.uint8[2],
    //     _vlc_mac_address.uint8[3],
    //     _vlc_mac_address.uint8[4],
    //     _vlc_mac_address.uint8[5]
    // );

    gnrc_netif_default_init(netif);
    /* save the threads context pointer, so we can set its flags */
    _netif_thread = thread_get_active();

}

// called when data needs to be send
static int _netif_send(gnrc_netif_t *netif, gnrc_pktsnip_t *pkt)
{
#ifdef DEBUG_OUT_PIN_SEND_LINK
    gpio_write(DEBUG_OUT_PIN_SEND_LINK, 1);
#endif

    (void) netif;
    assert(netif != NULL);
    assert(pkt != NULL);

    // bytes needed for link layer header
    int num_bytes_to_send = (2 * VLC_ADDR_LEN);

    DEBUG_POS("ENTER _netif_send\n");

    // first pktsnip must be a gnrc netif package
    assert(pkt->type == GNRC_NETTYPE_NETIF);
    if (!pkt) {
        num_bytes_to_send = -EBADMSG;
        puts("Error during send: pktsnip is NULL\n");
        goto end;
    }

    if (pkt->type != GNRC_NETTYPE_NETIF) {
        num_bytes_to_send = -EBADMSG;
        puts("Error during send: first pktsnip is not a netif herader\n");
        goto end;
    }

    // gnrc header does not need to be send, it contains information only relevant for gnrc_netif
    // link layer addresses etc.
    gnrc_netif_hdr_t *hdr = (gnrc_netif_hdr_t *)pkt->data;

    // do not send gnrc header, but store pointer to release it later
    gnrc_pktsnip_t *next_pkt = pkt->next;

    // add VLC mac header: source address + destination address
    memcpy(_send_buffer, &_vlc_mac_address, VLC_ADDR_LEN);

    uint8_t *mac_destination = gnrc_netif_hdr_get_dst_addr(hdr);
    if (mac_destination == NULL) {
        num_bytes_to_send = -EBADMSG;
        puts("Error during send: cannot read mac header\n");
        goto end;
    }
    DEBUG("send mac destination address: %02x:%02x:%02x:%02x:%02x:%02x\n", 
        mac_destination[0],
        mac_destination[1],
        mac_destination[2],
        mac_destination[3],
        mac_destination[4],
        mac_destination[5]
    );
    DEBUG("\n");
    memcpy(_send_buffer + VLC_ADDR_LEN, mac_destination, VLC_ADDR_LEN);

    // concatenate package data
    while (next_pkt) {

        // check if buffer is large enough, leave byte for CRC, header size already included
        if ((num_bytes_to_send + next_pkt->size) <= (VLC_BUFFER_SIZE - VLC_CRC_SIZE)) {
            memcpy(_send_buffer + num_bytes_to_send, next_pkt->data, (int) next_pkt->size);
        }
        else
        {
            num_bytes_to_send = -EMSGSIZE;
            puts("Error during send: payload too large\n");
            goto end;
        }
        DEBUG_POS("add data of package with data size %i to send buffer\n", next_pkt->size);

        num_bytes_to_send += (int) next_pkt->size;
        next_pkt = next_pkt->next;
    }

    // no error code
    assert (num_bytes_to_send >= 0);

    // TODO: compile only if measurement
    // NOTE: measurement block takes 484us
    // check if measurement marker is part of payload
    if ( ((unsigned int) num_bytes_to_send > sizeof(unsigned long int) + 1) && 
        (((u_int8_t *) _send_buffer)[num_bytes_to_send - (sizeof(unsigned long int) + 1)] == 'M')) {
        unsigned long int pkt_num;
        // decode package number from last 4 bytes
        memcpy(&pkt_num, _send_buffer + num_bytes_to_send - (sizeof(unsigned long int)), sizeof(unsigned long int));

        // unsigned irq_state = irq_disable();
        printf("sl %li\n", pkt_num);
        // irq_restore(irq_state);
    }

    // add crc trailer
    assert((num_bytes_to_send + VLC_CRC_SIZE) <= VLC_BUFFER_SIZE);
    uint8_t checksum = crc8((unsigned char *) _send_buffer, num_bytes_to_send, VLC_CRC_POLYNOM, VLC_CRC_INIT);
    DEBUG("send checksum %i\n", checksum);
    memcpy(_send_buffer + num_bytes_to_send, &checksum, sizeof(checksum));
    num_bytes_to_send += VLC_CRC_SIZE;

    // send if payload not empty
    if ((unsigned int) num_bytes_to_send > (2 * VLC_ADDR_LEN)) {
        // TODO: use variables for tolerance and sync bits
        DEBUG("vlc_netif: call vlc send\n");
        if (vlc_manchester_send(_send_buffer, num_bytes_to_send, DATARATE_BITS_PER_SECOND, 4) == 1) {
            // internal error e.g. during timer setup
            num_bytes_to_send = -EAGAIN;
            puts("Error during send: send returned error\n");
            goto end;
        }
    }
    else
    {
        num_bytes_to_send = -ENOTSUP;
        puts("Error during send: empty payload");
        goto end;
    }

end:
    gnrc_pktbuf_release(pkt);

#ifdef DEBUG_OUT_PIN_SEND_LINK
    gpio_write(DEBUG_OUT_PIN_SEND_LINK, 0);
#endif

    // TODO: also count mac layer header? Should be irrelevant, only used for netstats L2.
    return num_bytes_to_send;
}

static gnrc_pktsnip_t *_netif_recv(gnrc_netif_t *netif)
{

#ifdef DEBUG_OUT_PIN_RECV_LINK
    gpio_write(DEBUG_OUT_PIN_RECV_LINK, 1);
#endif

    DEBUG_POS("ENTER _netif_recv\n");
    DEBUG("received %i bytes (%i bit/s) from network device\n", _receive_meta_data.num_bytes_read, _receive_meta_data.data_rate);

    (void)netif;

    // message is now in receive buffer

    // check if header could exists
    if (_receive_meta_data.num_bytes_read <= (2 * VLC_ADDR_LEN) + VLC_CRC_SIZE) {
        DEBUG("vlc netif: received data to short for header with payload and crc trailer");
        vlc_reset_receiver();

#ifdef DEBUG_OUT_PIN_RECV_LINK
        gpio_write(DEBUG_OUT_PIN_RECV_LINK, 0);
        gpio_write(DEBUG_OUT_PIN_RECV_LINK, 1);
        gpio_write(DEBUG_OUT_PIN_RECV_LINK, 0);
#endif
        return NULL;
    }

    // should not happen, but check for later memory access
    if (_receive_meta_data.num_bytes_read >= VLC_BUFFER_SIZE) {
        DEBUG("vlc netif: received more data than buffer size");
        vlc_reset_receiver();

#ifdef DEBUG_OUT_PIN_RECV_LINK
        gpio_write(DEBUG_OUT_PIN_RECV_LINK, 0);
#endif
        return NULL;
    }

    // calculate checksum of header and payload
    uint8_t calculated_checksum = crc8(
        (unsigned char *) _receive_buffer,                  // address to check
        _receive_meta_data.num_bytes_read - VLC_CRC_SIZE,   // length of address to check
        VLC_CRC_POLYNOM,
        VLC_CRC_INIT
    );
    DEBUG("calculated checksum: %i\n", calculated_checksum);
    // read transmitted payload from crc trailer
    uint8_t received_checksum;
    memcpy(
        &received_checksum,
        _receive_buffer + _receive_meta_data.num_bytes_read - VLC_CRC_SIZE,
        sizeof(received_checksum)
    );
    DEBUG("read checksum: %i\n", received_checksum);    // check if checksums match
    if (received_checksum != calculated_checksum) {
        DEBUG("Received wrong checksum --> drop frame\n");
        vlc_reset_receiver();
#ifdef DEBUG_OUT_PIN_RECV_LINK
        gpio_write(DEBUG_OUT_PIN_RECV_LINK, 0);
        gpio_write(DEBUG_OUT_PIN_RECV_LINK, 1);
        gpio_write(DEBUG_OUT_PIN_RECV_LINK, 0);
        gpio_write(DEBUG_OUT_PIN_RECV_LINK, 1);
        gpio_write(DEBUG_OUT_PIN_RECV_LINK, 0);
#endif
        return NULL;
    }
    _receive_meta_data.num_bytes_read -= VLC_CRC_SIZE;

    // read VLC mac header: source address + destination address
    u_int8_t mac_source[VLC_ADDR_LEN];
    u_int8_t mac_destination[VLC_ADDR_LEN];
    memcpy(mac_source, _receive_buffer, VLC_ADDR_LEN);
    memcpy(mac_destination, _receive_buffer + VLC_ADDR_LEN, VLC_ADDR_LEN);

    // NOTE: addresses correctly transmitted, ping works --> check UDP
    // TODO: always wrong destination address
    // if (memcmp(mac_destination, _vlc_mac_address.uint8, VLC_ADDR_LEN) != 0) {
        // DEBUG("Received package with wrong destination\n");
    // }
    DEBUG("recv mac source  address: %02x:%02x:%02x:%02x:%02x:%02x\n", 
        mac_source[0],
        mac_source[1],
        mac_source[2],
        mac_source[3],
        mac_source[4],
        mac_source[5]
    );
    DEBUG("recv mac destination address: %02x:%02x:%02x:%02x:%02x:%02x\n", 
        mac_destination[0],
        mac_destination[1],
        mac_destination[2],
        mac_destination[3],
        mac_destination[4],
        mac_destination[5]
    );
    DEBUG("own mac address: %02x:%02x:%02x:%02x:%02x:%02x\n", 
        _vlc_mac_address.uint8[0],
        _vlc_mac_address.uint8[1],
        _vlc_mac_address.uint8[2],
        _vlc_mac_address.uint8[3],
        _vlc_mac_address.uint8[4],
        _vlc_mac_address.uint8[5]
    );
    DEBUG("\n");

    // create netif header pktsnip
    gnrc_pktsnip_t *netif_header = gnrc_netif_hdr_build(mac_source, VLC_ADDR_LEN, mac_destination, VLC_ADDR_LEN);
    if (netif_header == NULL) {
        DEBUG("ERROR: failed to allocate netif_header!\n");
        vlc_reset_receiver();

#ifdef DEBUG_OUT_PIN_RECV_LINK
        gpio_write(DEBUG_OUT_PIN_RECV_LINK, 0);
#endif

        return NULL;
    }
    gnrc_netif_hdr_set_netif(netif_header->data, netif);

    gnrc_pktsnip_t *received_data_pkt;

    received_data_pkt = gnrc_pktbuf_add(netif_header, _receive_buffer + (2 * VLC_ADDR_LEN), _receive_meta_data.num_bytes_read - (2 * VLC_ADDR_LEN), GNRC_NETTYPE_IPV6);
    if (received_data_pkt == NULL) {
        DEBUG("ERROR: failed to allocate package for received data!\n");
        gnrc_pktbuf_release(netif_header);
        vlc_reset_receiver();

#ifdef DEBUG_OUT_PIN_RECV_LINK
        gpio_write(DEBUG_OUT_PIN_RECV_LINK, 0);
#endif
        return NULL;
    }
    // content of _receive_buffer is now copied using gnrc_pktbuf_add

    // TODO: compile only if measurement
    // check if measurement marker is part of payload
    if ( ((unsigned int) _receive_meta_data.num_bytes_read > sizeof(unsigned long int) + 1) && 
        (((u_int8_t *) _receive_buffer)[_receive_meta_data.num_bytes_read - (sizeof(unsigned long int) + 1)] == 'M')) {
        unsigned long int pkt_num;
        // decode package number from last 4 bytes
        memcpy(&pkt_num, _receive_buffer + _receive_meta_data.num_bytes_read - (sizeof(unsigned long int)), sizeof(unsigned long int));

        // unsigned irq_state = irq_disable();
        printf("rl %li\n", pkt_num);
        // irq_restore(irq_state);
    }

    vlc_reset_receiver();

#ifdef DEBUG_OUT_PIN_RECV_LINK
    gpio_write(DEBUG_OUT_PIN_RECV_LINK, 0);
#endif

    return received_data_pkt;
    // return gnrc_pkt_append(received_data_pkt, netif_header);
}

// network intrterface operations
static const gnrc_netif_ops_t _vlc_netif_ops = {
    .init = _netif_init,
    .send = _netif_send,
    .recv = _netif_recv,
    .get = gnrc_netif_get_from_netdev,
    .set = gnrc_netif_set_from_netdev,
    .msg_handler = NULL,
};

static inline int _netdev_init(netdev_t *dev)
{
    DEBUG_POS("ENTER _netdev_init\n");

    // TODO: pass input pin to driver

    // TODO: use variables or defines
    _dev_receive_conf.tolerance = VLC_RECEIVER_TOLERANCE;
    _dev_receive_conf.num_sync_symbols = 4;
    _dev_receive_conf.synchronous = 0;       // asynchronous
    _dev_receive_conf.netdev = dev;
    _dev_receive_conf.buffer_size = VLC_BUFFER_SIZE;

    vlc_init_receiver(_receive_buffer, _dev_receive_conf, &_receive_meta_data);

    if (vlc_mancheser_init() > 0) {
        puts("Error cannot init vlc netdev");
        return -1;
    };

    return 0;
}

static inline int _netdev_get(netdev_t *dev, netopt_t opt,
                              void *value, size_t max_len)
{
    DEBUG_POS("ENTER _netdev_get\n");

    (void) dev;
    (void) opt;
    (void) value;
    (void) max_len;

    int res = -ENOTSUP;

    switch (opt) {
        case NETOPT_ADDRESS:
            assert(max_len >= VLC_ADDR_LEN);
            memcpy(value, _vlc_mac_address.uint8, VLC_ADDR_LEN);
            res = VLC_ADDR_LEN;
            DEBUG_POS("NETOPT_ADDRESS\n");
            break;
        case NETOPT_ADDR_LEN:
        case NETOPT_SRC_LEN:
            assert(max_len == sizeof(uint16_t));
            *((uint16_t *)value) = VLC_ADDR_LEN;
            res = sizeof(uint16_t);
            DEBUG_POS("NETOPT_SRC_LEN or NETOPT_ADDR_LEN\n");
            break;
        case NETOPT_MAX_PDU_SIZE:   // protocol data unit size
            assert(max_len >= sizeof(uint16_t));
            *((uint16_t *)value) = MTU_SIZE;
            res = sizeof(uint16_t);
            DEBUG_POS("NETOPT_MAX_PDU_SIZE\n");
            break;
        case NETOPT_PROTO:
            assert(max_len == sizeof(gnrc_nettype_t));
            *((gnrc_nettype_t *)value) = _nettype;
            res = sizeof(gnrc_nettype_t);
            DEBUG_POS("NETOPT_PROTO\n");
            break;
        case NETOPT_DEVICE_TYPE:
            assert(max_len == sizeof(uint16_t));
            *((uint16_t *)value) = NETDEV_TYPE_VLC;    // TODO: geht nicht weil TEST_SUITES nicht definiert
            res = sizeof(uint16_t);
            DEBUG_POS("NETOPT_DEVICE_TYPE\n");
            break;
        default:
            break;
    }

    return res;
}

static inline int _netdev_set(netdev_t *dev, netopt_t opt,
                              const void *value, size_t val_len)
{
    DEBUG_POS("ENTER _netdev_set\n");

    // during initialization this is called by _configure_netdev
    // and it sets the RX and TX complete interrupts
    // NETOPT_RX_END_IRQ and NETOPT_TX_END_IRQ
    // TODO: needed?

    (void) dev;
    (void) opt;
    (void) value;
    (void) val_len;

    (void)dev;
    int res = -ENOTSUP;

    switch (opt) {
        case NETOPT_PROTO:
            assert(val_len == sizeof(_nettype));
            memcpy(&_nettype, value, sizeof(_nettype));
            res = sizeof(_nettype);
            break;
        default:
            break;
    }

    return res;
}

static void _on_isr(netdev_t *dev)
{
    DEBUG_POS("ENTER _on_isr\n");
    // printf("data received!\n");

    // TODO: handle NETDEV_EVENT_RX_STARTED, NETDEV_EVENT_RX_TIMEOUT
    // NOTE: this event callback is defined in gnrc_netif.c
    dev->event_callback(dev, NETDEV_EVENT_RX_COMPLETE);
}

static const netdev_driver_t _vlc_netdev_driver = {
    .send = NULL,
    .recv = NULL,
    .init = _netdev_init,
    .isr  = _on_isr,           // event callback if device isr signals start or end of transmission
    .get  = _netdev_get,
    .set  = _netdev_set,
};

static netdev_t _vlc_netdev_dummy = {
    .driver = &_vlc_netdev_driver,
};

// no interface
void vlc_netif_init(void)
{

#ifdef DEBUG_OUT_PIN_SEND_LINK
    if (gpio_init(DEBUG_OUT_PIN_SEND_LINK, GPIO_OUT) < 0) {
        puts("vlc init send: gpio init returns an error");
        return;
    }
#endif

#ifdef DEBUG_OUT_PIN_RECV_LINK 
    if (gpio_init(DEBUG_OUT_PIN_RECV_LINK, GPIO_OUT) < 0) {
        puts("vlc init send: gpio init returns an error");
        return;
    }
#endif

    DEBUG_POS("ENTER vlc_netif_init\n");

    // starts thread with eventloop
    gnrc_netif_create(&_netif, _stack, sizeof(_stack), GNRC_NETIF_PRIO,
                      "vlc_netif", &_vlc_netdev_dummy, &_vlc_netif_ops);
}
