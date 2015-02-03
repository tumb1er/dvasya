# coding: utf-8

# $Id: $

# dvasya logging configurator module
#
# when imported, configures python logging with config defined in
# dvasya.conf.LOGGING variable
#
# All configuration code is ported from Django
# http://djangoproject.com
#
# P.S. filters for loggers and handlers are not supported.
from copy import deepcopy

import logging
import sys
from dvasya.conf import settings
from dvasya.utils import import_object

__all__ = ['getLogger']


getLogger = logging.getLogger

LOGGING = deepcopy(settings.LOGGING)


def common_logger_config(logger_config, logger, incremental=False):
    """
    Perform configuration which is common to root and non-root loggers.
    """
    level = logger_config.get('level', None)
    if level is not None:
        logger.setLevel(logging._checkLevel(level))
    if not incremental:
        # Remove any existing handlers
        for h in logger.handlers[:]:
            logger.removeHandler(h)
        handlers = logger_config.get('handlers', None)
        if handlers:
            add_handlers(logger, handlers)


def configure_logger(name, logger_config, incremental=False):
    """Configure a non-root logger from a dictionary."""
    logger = logging.getLogger(name)
    common_logger_config(logger_config, logger, incremental)
    propagate = LOGGING.get('propagate', None)
    if propagate is not None:
        logger.propagate = propagate


def add_handlers(logger, handlers):
    """Add handlers to a logger from a list of names."""
    for h in handlers:
        try:
            logger.addHandler(LOGGING['handlers'][h])
        except Exception as e:
            raise ValueError('Unable to add handler %r: %s' % (h, e))


def configure_handler(handler_config):
    """Configure a handler from a dictionary."""
    formatter = handler_config.pop('formatter', None)
    if formatter:
        try:
            formatter = LOGGING['formatters'][formatter]
        except Exception as e:
            raise ValueError('Unable to set formatter '
                             '%r: %s' % (formatter, e))
    level = handler_config.pop('level', None)
    klass = import_object(handler_config.pop('class'))
    factory = klass
    kwargs = dict([(k, handler_config[k]) for k in handler_config])
    result = factory(**kwargs)
    if formatter:
        result.setFormatter(formatter)
    if level is not None:
        result.setLevel(logging._checkLevel(level))
    return result


def configure_root(logger_config, incremental=False):
    """Configure a root logger from a dictionary."""
    root = logging.getLogger()
    common_logger_config(logger_config, root, incremental)


def configure_formatter(formatter_config):
    """Configure a formatter from a dictionary."""
    fmt = formatter_config.get('format', None)
    dfmt = formatter_config.get('datefmt', None)
    result = logging.Formatter(fmt, dfmt)
    return result


def configure():
    """Do the configuration."""
    config = LOGGING
    incremental = config.pop('incremental', False)
    EMPTY_DICT = {}
    logging._acquireLock()
    try:
        if incremental:
            handlers = config.get('handlers', EMPTY_DICT)
            # incremental handler config only if handler name
            # ties in to logging._handlers (Python 2.7)
            if sys.version_info[:2] == (2, 7):
                for name in handlers:
                    if name not in logging._handlers:
                        raise ValueError('No handler found with '
                                         'name %r' % name)
                    else:
                        try:
                            handler = logging._handlers[name]
                            handler_config = handlers[name]
                            level = handler_config.get('level', None)
                            if level:
                                handler.setLevel(logging._checkLevel(level))
                        except Exception as e:
                            raise ValueError('Unable to configure handler '
                                             '%r: %s' % (name, e))
            loggers = config.get('loggers', EMPTY_DICT)
            for name in loggers:
                try:
                    configure_logger(name, loggers[name], True)
                except Exception as e:
                    raise ValueError('Unable to configure logger '
                                     '%r: %s' % (name, e))
            root = config.get('root', None)
            if root:
                try:
                    configure_root(root, True)
                except Exception as e:
                    raise ValueError('Unable to configure root '
                                     'logger: %s' % e)
        else:
            disable_existing = config.pop('disable_existing_loggers', True)

            logging._handlers.clear()
            del logging._handlerList[:]

            # Do formatters first - they don't refer to anything else
            formatters = config.get('formatters', EMPTY_DICT)
            for name in formatters:
                try:
                    formatters[name] = configure_formatter(
                        formatters[name])
                except Exception as e:
                    raise ValueError('Unable to configure '
                                     'formatter %r: %s' % (name, e))

            # Next, do handlers - they refer to formatters and filters
            # As handlers can refer to other handlers, sort the keys
            # to allow a deterministic order of configuration
            handlers = config.get('handlers', EMPTY_DICT)
            for name in sorted(handlers):
                try:
                    handler = configure_handler(handlers[name])
                    handler.name = name
                    handlers[name] = handler
                except Exception as e:
                    raise ValueError('Unable to configure handler '
                                     '%r: %s' % (name, e))
            # Next, do loggers - they refer to handlers and filters

            # we don't want to lose the existing loggers,
            # since other threads may have pointers to them.
            # existing is set to contain all existing loggers,
            # and as we go through the new configuration we
            # remove any which are configured. At the end,
            # what's left in existing is the set of loggers
            # which were in the previous configuration but
            # which are not in the new configuration.
            root = logging.root
            existing = list(root.manager.loggerDict)
            # The list needs to be sorted so that we can
            # avoid disabling child loggers of explicitly
            # named loggers. With a sorted list it is easier
            # to find the child loggers.
            existing.sort()
            # We'll keep the list of existing loggers
            # which are children of named loggers here...
            child_loggers = []
            # now set up the new ones...
            loggers = config.get('loggers', EMPTY_DICT)
            for name in loggers:
                if name in existing:
                    i = existing.index(name)
                    prefixed = name + "."
                    pflen = len(prefixed)
                    num_existing = len(existing)
                    i = i + 1  # look at the entry after name
                    while (i < num_existing) and \
                            (existing[i][:pflen] == prefixed):
                        child_loggers.append(existing[i])
                        i = i + 1
                    existing.remove(name)
                try:
                    configure_logger(name, loggers[name])
                except Exception as e:
                    raise ValueError('Unable to configure logger '
                                     '%r: %s' % (name, e))

            # Disable any old loggers. There's no point deleting
            # them as other threads may continue to hold references
            # and by disabling them, you stop them doing any logging.
            # However, don't disable children of named loggers, as that's
            # probably not what was intended by the user.
            for log in existing:
                logger = root.manager.loggerDict[log]
                if log in child_loggers:
                    logger.level = logging.NOTSET
                    logger.handlers = []
                    logger.propagate = True
                elif disable_existing:
                    logger.disabled = True

            # And finally, do the root logger
            root = config.get('root', None)
            if root:
                try:
                    configure_root(root)
                except Exception as e:
                    raise ValueError('Unable to configure root '
                                     'logger: %s' % e)
    finally:
        logging._releaseLock()

configure()
