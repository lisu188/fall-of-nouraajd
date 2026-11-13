FROM ubuntu@sha256:a3785f78ab8547ae2710c89e627783cfa7ee7824d3468cae6835c9f4eae23ff7

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get -o Acquire::Check-Valid-Until=false update && \
    apt-get install -y --no-install-recommends \
        build-essential gcc-5=5.4.0-6ubuntu1~16.04.12 g++-5=5.4.0-6ubuntu1~16.04.12 \
        qtbase5-dev=5.5.1+dfsg-16ubuntu7.7 qtbase5-dev-tools=5.5.1+dfsg-16ubuntu7.7 \
        qt5-qmake=5.5.1+dfsg-16ubuntu7.7 libqt5opengl5-dev=5.5.1+dfsg-16ubuntu7.7 \
        ca-certificates curl xz-utils bzip2 make python3 \
        git=1:2.7.4-0ubuntu1.10 libssl-dev=1.0.2g-1ubuntu4.20 \
        zlib1g-dev=1:1.2.8.dfsg-2ubuntu4.3 libffi-dev libbz2-dev libreadline-dev \
        libsqlite3-dev libncurses5-dev uuid-dev libgl1-mesa-dri libgl1-mesa-glx xvfb xauth && \
    dpkg-query -W > /opt/recovery-installed-packages.txt && \
    rm -rf /var/lib/apt/lists/*

COPY sources.json build.sh /opt/recovery/toolchain-source/
RUN bash /opt/recovery/toolchain-source/build.sh

ENV LIBGL_ALWAYS_SOFTWARE=1 QT_OPENGL=software QT_X11_NO_MITSHM=1
WORKDIR /workspace
ENTRYPOINT ["/opt/recovery/controller/bin/python3.12"]
