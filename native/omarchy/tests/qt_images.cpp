// SPDX-License-Identifier: BSD-3-Clause
// Decode only the pinned, public upstream background; never user media.
#include <QCoreApplication>
#include <QImageReader>
#include <cstdio>
#include <unistd.h>

int main(int argc, char** argv) {
    if (getuid() == 0) return 1;
    QCoreApplication app(argc, argv);
    QImageReader::setAllocationLimit(128);
    const QString source = "/workspace/build/omarchy-sources/omarchy/themes/tokyo-night/backgrounds/0-winding-road.webp";
    QImageReader reader(source);
    if (reader.format() != "webp" || !reader.canRead()) {
        std::fprintf(stderr, "Qt cannot decode original WebP background: %s\n", qPrintable(reader.errorString()));
        return 1;
    }
    const QImage image = reader.read();
    if (image.isNull() || image.width() <= 1 || image.height() <= 1 || image.sizeInBytes() > 128 * 1024 * 1024)
        return 1;
    std::printf("Original background decoded uid=%u Qt=%s format=webp size=%dx%d bytes=%lld\n",
                getuid(), qVersion(), image.width(), image.height(), static_cast<long long>(image.sizeInBytes()));
    return 0;
}
