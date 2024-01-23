from tony import main
import tornado

## Run the loop
tornado.ioloop.IOLoop.current().run_sync(main)