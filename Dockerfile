FROM jrottenberg/ffmpeg:6.1-alpine

COPY stitch.sh /usr/local/bin/stitch.sh
RUN chmod +x /usr/local/bin/stitch.sh

WORKDIR /videos

ENTRYPOINT ["/usr/local/bin/stitch.sh"]
