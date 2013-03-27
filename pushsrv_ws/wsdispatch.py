# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from .constants import LOG
import uuid


class WSDispatch():
    """ Very simple message dispatcher.

        It stores a callback for each registered UAID. Please note that
        this may be replaced with a different dispatch system, or
        subclassed to provide proprietary callback system.
    """

    _uaids={}

    def __init__(self, config={}, flags={}):
        pass

    def _uuid2idx(self, uaid):
        """ Convert a UUID back to it's byte array equivalent.

            (This requires slightly less space to store and is optional)
        """
        try:
            idx = uuid.UUID(uaid).bytes
        except:
            idx = uaid
        return idx

    def register(self, uaid, callback, extra={}):
        """ Register a new client as a listener.
        """

        ## If there are additional, proprietary driver steps and
        ## requirements (e.g. register UDP wakeup calls), that
        ## information should be stored using the "extra" param.
        idx = self._uuid2idx(uaid)
        if idx in self._uaids.keys():
            self.release(uaid)
        self._uaids[idx] = callback
        return True

    def queue(self, uaid, channelID):
        """ Submit an event for a given device queue

            Remember, events are actions. If there is data to track
            place into storage first!
        """
        idx = self._uuid2idx(uaid)
        try:
            ## if it's a live queue, send the message.
            if self._uaids[idx](uaid=uaid, channelID=channelID):
                return True
        except Exception, e:
            ## There was a problem, (Most likely a key error)
            ## Perform whatever proprietary steps are required in
            ## order to wake the remote device. On device reconnect
            ## the pending events are flushed to the device.
            self.logger.log(type='warning', severity=LOG.WARNING,
                            error=e)
            self.wakeDevice()
            pass
        return False

    def release(self, uaid):
        """ release a listener from actively monitoring
        """
        idx = self._uuid2idx(uaid)
        del self._uaids[idx]

    def wakeDevice(self):
        """ Wake a remote device using any proprietary driver steps
            required.
        """
        ## There are no means defined by default to wake a device
        pass

