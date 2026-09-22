// lzo_scan.c - scan a blob for a raw LZO1X stream at candidate offsets
// usage: lzo_scan <file> [maxoff] [expectsize]
// uses lzo1x_decompress_safe (bounds-checked, no segfaults)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <lzo/lzo1x.h>

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s file [maxoff] [expectsize]\n", argv[0]); return 1; }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("open"); return 1; }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    unsigned char *in = malloc(sz);
    if (fread(in, 1, sz, f) != (size_t)sz) { fprintf(stderr, "short read\n"); return 1; }
    fclose(f);
    long maxoff = argc > 2 ? atol(argv[2]) : 0x10000;
    long expect = argc > 3 ? atol(argv[3]) : 0;
    if (maxoff > sz) maxoff = sz;

    size_t osize = 32u * 1024 * 1024;
    unsigned char *out = malloc(osize);
    static unsigned char wrkmem[64 * 1024];
    lzo_init();
    int hits = 0;
    for (long off = 0; off <= maxoff; off++) {
        if (off + 8 > sz) break;
        lzo_uint obyt = (lzo_uint)osize; /* safe variant: in = max capacity, out = actual */
        int r = lzo1x_decompress_safe(in + off, (lzo_uint)(sz - off), out, &obyt, wrkmem);
        if (r == LZO_E_OK && obyt > 64) {
            int interesting = obyt > 100000 ||
                              (out[0] == '0' && out[1] == '7' && out[2] == '7') ||
                              (expect && (long)obyt == expect);
            if (interesting) {
                printf("offset %ld (0x%lx) -> OK %lu bytes  head=", off, off, (unsigned long)obyt);
                for (int i = 0; i < 16; i++) printf("%02x", out[i]);
                printf("\n  ascii=%.40s\n", out);
                if (obyt > 100000 || (out[0] == '0' && out[1] == '7')) {
                    char fn[256];
                    snprintf(fn, sizeof fn, "out_%06ld.bin", off);
                    FILE *o = fopen(fn, "wb");
                    fwrite(out, 1, obyt, o); fclose(o);
                    printf("  ** wrote %s\n", fn);
                    hits++;
                }
            }
        }
    }
    if (!hits) printf("no interesting LZO1X stream found (scanned 0..0x%lx)\n", maxoff);
    return 0;
}
