SimplePush Websocket server (in python)
===

This version uses WebSockets to communicate with the client.

See https://wiki.mozilla.org/WebAPI/SimplePush for details

NOTE: This server is initially configured for stand-alone use.

Building
---
$make build

Running
---
$make run

Customizing
---
If you wish to add proprietary wake up functions, you may wish to subclass the
pushsrv\_ws/wsdispatch.py WSDispatch function.

Calling
---

