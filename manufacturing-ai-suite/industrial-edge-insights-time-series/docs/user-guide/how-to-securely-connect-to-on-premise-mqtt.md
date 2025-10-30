
# Configuration to securely connect to MQTT endpoint

Follow the below steps to securely connet to the on premise MQTT endpoint for ingestion and publishing alerts.

1. Generate the server certificates.

```bash
cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series
source ./.env
mkdir -p certs
sudo rm -rf ./certs/*

cd certs
EXTERNAL_MQTT_BROKER_HOST=192.168.1.100  # Replace with your MQTT broker IP

# Generate CA key and certificate
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 365 -key ca.key -out ca_cert.pem -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=MQTT-CA"
cp ca_cert.pem ca_certificate.em

openssl genrsa -out server.key 4096
openssl req -new -key server.key -out server.csr -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=$EXTERNAL_MQTT_BROKER_HOST"

cat > server.ext << EOF
[v3_req]
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = $EXTERNAL_MQTT_BROKER_HOST
DNS.2 = localhost
IP.1 = 127.0.0.1
EOF

openssl x509 -req -in server.csr -CA ca_certificate.pem -CAkey ca.key -CAcreateserial -out server_certificate.pem -days 365 -extensions v3_req -extfile server.ext

sudo chown $TIMESERIES_UID:$TIMESERIES_UID ca_certificate.pem
```

2. Volume mount the generated certificates

Volume mount the generated `ca_certificate.pem` to the `ia-telegraf, ia-time-series-analytics-microservice` and `ia-mqtt-publisher` docker containers.
Make the below changes in `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/docker-compose.yml` file.

```yaml
...
ia-telegraf:
  volumes:
  ...
  - ./certs/ca_certificate.pem:/run/secrets/ca_certificate.pem

ia-time-series-analytics-microservice:
  volumes:
  ...
  - ./certs/ca_certificate.pem:/run/secrets/ca_certificate.pem

ia-mqtt-publisher:
  volumes:
  ...
  - ./certs/ca_certificate.pem:/run/secrets/ca_certificate.pem
```

3. Changes to Telegraf.conf

Update the `EXTERNAL_MQTT_BROKER_HOST` in `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/<sample_app>/telegraf-config/Telegraf.conf`

Make the below changes to the file. Replace the EXTERNAL_MQTT_BROKER_HOST and EXTERNAL_MQTT_BROKER_PORT with the MQTT broker host and port. And add the `tls-ca` key to refer the `ca_certificate.pem` 
```
 [[inputs.mqtt_consumer]]
#   ## MQTT broker URLs to be used. The format should be scheme://host:port,
#   ## schema can be tcp, ssl, or ws.
    servers = ["ssl://<EXTERNAL_MQTT_BROKER_HOST>:<EXTERNAL_MQTT_BROKER_PORT>"]
    tls_ca = "/run/secrets/ca_certificate.pem"
```

4. Changes to kapacitor_devmode.conf

Replace the `url` with the below change and add `ssl-ca` key to refer the `ca_certificate.pem` in the `edge-ai-libraries/microservices/time-series-analytics/config/kapacitor_devmode.conf` file.

```
[[mqtt]]
  enabled = true
  # Unique name for this broker configuration
  name = "my_mqtt_broker"
  # Whether this broker configuration is the default
  default = true
  # URL of the MQTT broker.
  # Possible protocols include:
  #  tcp - Raw TCP network connection
  #  ssl - TLS protected TCP network connection
  #  ws  - Websocket network connection
  url = "ssl://MQTT_BROKER_HOST:MQTT_BROKER_PORT"

  # TLS/SSL configuration
  # A CA can be provided without a key/cert pair
  ssl-ca = "/run/secrets/ca_certificate.pem"
```

5. Changes to `config.json`

Update the external MQTT broker host and port in the `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/<sample_app>/time-series-analytics-config/config.json` alerts section.

```
"alerts": {
        "mqtt": {
            "mqtt_broker_host": "<mqtt broker host>",
            "mqtt_broker_port": <mqtt broker port>,
            "name": "my_mqtt_broker"
        }
    }
```

6. Volume mount the `kapacitor_devmode.conf`

Volume mount the `edge-ai-libraries/microservices/time-series-analytics/config/kapacitor_devmode.conf` file in the `ia-time-series-analytics-microservice` container.
Make the below changes to the `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/docker-compose.yml` file.

```yaml
ia-time-series-analytics-microservice:
  volumes:
  - <absolute path to kapacitor_devmode.conf>:/app/config/kapacitor_devmode.conf
```

7. Comment the `ia-mqtt-broker` from the `depends_on` key in the `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/docker-compose.yml` file.
Eg is shown for the `ia-time-series-analytics-microservice` service.

```yaml
ia-time-series-analytics-microservice:
  depends_on:
      - ia-influxdb
      # - ia-mqtt-broker
```

8. Comment the `ia-mqtt-broker` service in the edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/docker-compose.yml` file as shown below.

```yaml
# ia-mqtt-broker:
  #   user: "${TIMESERIES_UID}:${TIMESERIES_UID}"
  #   container_name: ia-mqtt-broker
  #   hostname: ia-mqtt-broker
  #   read_only: true
  #   image: eclipse-mosquitto:2.0.21
  #   restart: unless-stopped
  #   depends_on:
  #     - ia-influxdb
  #   security_opt:
  #   - no-new-privileges
  #   healthcheck:
  #     test: ["CMD-SHELL", "exit", "0"]
  #     interval: 5m
  #   networks:
  #   - timeseries_network
  #   volumes:
  #   - ./configs/mqtt-broker/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
  #   - ./certs:/run/secrets:ro

```

10. Replace `ia-mqtt-broker` in the `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/docker-compose.yml` file with the external mqtt broker host ip.
Example is as shown below.

```yaml
ia-telegraf:
  environment:
      no_proxy: "ia-influxdb,192.168.1.100,ia-opcua-server,ia-time-series-analytics-microservice,${no_proxy}"
      NO_PROXY: "ia-influxdb,192.168.1.100,ia-opcua-server,ia-time-series-analytics-microservice,${no_proxy}"
```

11. Add environment variable `PORT` to the `ia-mqtt-publisher` service as shown below in the `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/docker-compose.yml` file.
Assign value of the external mqtt broker port to this variable.

```yaml
ia-mqtt-publisher:
  environment:
    AppName: "mqtt-publisher"
    PORT: 8000
```

12. Update the external mqtt broker port in the nginx service in `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/docker-compose.yml` file.
Below is an example shown with port number 8000.

```yaml
nginx:
  ports:
  - 8000:8000
```

13. Update the `nginx.conf` file.

Replace the `ia-mqtt-broker` with the external mqtt broker ip and `1883` with the external mqtt broker port number  in the `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/configs/nginx/nginx.conf` file.

14. Deploy the sample application following the steps as mentioned [here](./get-started.md#deploy-with-docker-compose)