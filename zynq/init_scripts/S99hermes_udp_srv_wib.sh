echo "Starting Hermes IPBus UDP server"
/bin/hermes_udp_srv -d wib -c false 2>/var/log/hermes_udp_srv.err >/var/log/hermes_udp_srv.log &