# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import absolute_import, print_function, unicode_literals

import datetime
import logging
import sys

import hglib
import kombu

from .config import (
    Config,
)
from .consumer import (
    Consumer,
)
from .daemon import (
    run_in_loop,
)
from .pushnotifications import (
    consume_one,
)


logger = logging.getLogger('vcsreplicator.pulsenotifier')


def send_pulse_message(config, exchange, repo_url, payload):
    """Send a pulse message for a repository event.

    The Pulse host configured by the config object will be connected to.
    The routing key will be constructed from the repository URL.
    The Pulse message will be constructed from the specified payload
    and sent to the requested exchange.
    """
    c = config.c

    routing_key_strip_prefix = c.get('pulse', 'routing_key_strip_prefix')
    if not repo_url.startswith(routing_key_strip_prefix):
        raise Exception('repo URL does not begin with %s: %s' % (
            routing_key_strip_prefix, repo_url))

    routing_key = repo_url[len(routing_key_strip_prefix):]

    hostname = c.get('pulse', 'hostname')
    port = c.getint('pulse', 'port')
    userid = c.get('pulse', 'userid')

    logger.warn('connecting to pulse at %s:%d as %s' % (hostname, port, userid))

    conn = kombu.Connection(hostname=hostname,
                            port=port,
                            userid=userid,
                            password=c.get('pulse', 'password'),
                            virtual_host=c.get('pulse', 'virtual_host'),
                            ssl=c.getboolean('pulse', 'ssl'),
                            connect_timeout=c.getint('pulse', 'connect_timeout'))
    conn.connect()
    with conn:
        ex = kombu.Exchange(exchange, type='topic')
        producer = conn.Producer(exchange=ex,
                                 routing_key=routing_key,
                                 serializer='json')

        data = {
            'payload': payload,
            '_meta': {
                'exchange': exchange,
                'routing_key': routing_key,
                'serializer': 'json',
                'sent': datetime.datetime.utcnow().isoformat(),
            }
        }

        logger.warn('publishing message to %s#%s' % (exchange, routing_key))
        producer.publish(data)


def on_event(config, message_type, data):
    """Called when a replication message should be handled."""
    repo_url = data['repo_url']
    logger.warn('sending pulse notification for %s' % repo_url)

    # v1 of the exchange only supported a single message type that corresponded
    # to ``changegroup.1`` messages. So only send these messages to that
    # exchange.
    if message_type == 'changegroup.1':
        # Lock the old message type and prevent new keys from being added.
        sanitized = {k: v for k, v in data.items()
                     if k in ('repo_url', 'heads', 'pushlog_pushes')}
        exchange = config.c.get('pulse', 'exchange')
        send_pulse_message(config, exchange, repo_url, sanitized)

    # It's worth noting that we don't ack the message until sent to all
    # exchanges. This means if there is success sending to a exchange and
    # a failure occurs before sending to all exchanges, the message will
    # almost certainly be re-processed later and there will be double delivery
    # of the message to the early exchange(s). This is technically acceptable
    # because we guarantee at-least-once delivery. However, not all downstream
    # systems may appreciate the redundant copies. Having the latest version
    # of the exchange last provides an incentive for consumers to move to it,
    # as it will receive the fewest duplicate deliveries. However, that's not
    # a great workaround. If duplicate deliveries become a problem, we should
    # split the per-exchange delivery into separate mechanisms so each has an
    # independent consumer+offset in Kafka.

    # Version 2 of the exchange adds the message type to the payload so
    # multiple message types can be published.
    exchange2 = config.c.get('pulse', 'exchange2')
    send_pulse_message(config, exchange2, repo_url, {
        'type': message_type,
        'data': data,
    })


def cli():
    """Command line interface to run the Pulse notification daemon."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('config', help='Path to config file to load')
    parser.add_argument('--skip', action='store_true',
                        help='Skip the consuming of the next message then exit')
    args = parser.parse_args()

    config = Config(filename=args.config)

    if not config.c.has_section('pulse'):
        print('no [pulse] config section')
        sys.exit(1)

    group = config.c.get('pulseconsumer', 'group')
    topic = config.c.get('pulseconsumer', 'topic')

    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(name)s %(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # hglib will use 'hg' which relies on PATH being correct. Since we're
    # running from a virtualenv, PATH may not be set unless the virtualenv
    # is activated. Overwrite the hglib defaults with a value from the config.
    hglib.HGPATH = config.hg_path

    client = config.get_client_from_section('pulseconsumer', timeout=5)

    with Consumer(client, group, topic, partitions=None) as consumer:
        if args.skip:
            r = consumer.get_message()
            if not r:
                print('no message available; nothing to skip')
                sys.exit(1)

            partition = r[0]

            try:
                message_type = r[2]['name']
            except Exception:
                message_type = 'UNKNOWN'

            consumer.commit(partitions=[partition])
            print('skipped %s message in partition %d for group %s' % (
                message_type, partition, group))
            sys.exit(0)

        cbkwargs = {
            'config': config,
        }
        res = run_in_loop(logger, consume_one, config=config, consumer=consumer,
                          cb=on_event, cbkwargs=cbkwargs)

    logger.warn('process exiting code %s' % res)
    sys.exit(res)
