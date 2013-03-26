from .constants import LOG
import uuid


class WSDispatch():
    """ Very simple message dispatcher.

        It stores a callback for each registered UAID.
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

    def wakeDevice(self):
        """ Wake a remote device using any proprietary driver steps
            required.
        """
        # There are no means defined by default to wake a device
        pass

    def register(self, uaid, callback, extra={}):
        """ Register a new client as a listener.
        """

        ## If there are additional, proprietary driver steps and
        ## requirements (e.g. register UDP wakeup calls).
        idx = self._uuid2idx(uaid)
        if idx not in self._uaids.keys():
            self._uaids[idx] = callback
            return True
        return False

    def queue(self, uaid, channelID):
        """ Submit an update request  for a given device queue

            Remember, this is a store and forward system. Be sure to
            store the update into storage first!
        """
        idx = self._uuid2idx(uaid)
        try:
            ## if it's a live queue, send the message.
            if self._uaids[idx](uaid=uaid, channelID=channelID):
                return True
        except Exception, e:
            # There was a problem, (Most likely a key error
            # Perform whatever proprietary steps are required in
            # order to wake the remote device
            self.logger.log(type='warning', severity=LOG.WARNING,
                            error=e)
            self.wakeDevice()
            pass
        return False

    def release(self, uaid):
        idx = self._uuid2idx(uaid)
        del self._uaids[idx]



