#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <lzo/lzo1x.h>

int main(int argc,char**argv){
    if(argc<2){fprintf(stderr,"usage: %s file [maxoff]\n",argv[0]);return 1;}
    FILE*f=fopen(argv[1],"rb"); if(!f){perror("open");return 1;}
    fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET);
    unsigned char*in=malloc(sz);
    if(fread(in,1,sz,f)!=sz){fprintf(stderr,"short read\n");return 1;}
    fclose(f);
    long maxoff=argc>2?atol(argv[2]):0x10000;
    if(maxoff>sz)maxoff=sz;

    size_t osize=16u*1024*1024;
    unsigned char*out=malloc(osize);
    static unsigned char wrkmem[64*1024];
    lzo_init();
    int found=0;
    for(long off=0; off<=maxoff && !found; off++){
        if(off+8>sz)break;
        unsigned char*dst=out; size_t obyt=0;
        int r=lzo1x_decompress(in+off, (lzo_uint)(sz-off), dst, (lzo_uint*)&obyt, wrkmem);
        if(r==LZO_E_OK && obyt>64){
            printf("offset %ld (0x%lx) -> OK %zu bytes  head=",off,off,obyt);
            for(int i=0;i<16;i++)printf("%02x",dst[i]);
            printf("  ascii=%.16s\n",dst);
            if(dst[0]=='0'&&dst[1]=='7'&&dst[2]=='7'){
                char fn[256]; snprintf(fn,sizeof fn,"rootfs_out_%ld.cpio",off);
                FILE*o=fopen(fn,"wb"); fwrite(out,1,obyt,o); fclose(o);
                printf("   ** looks like cpio -> wrote %s\n",fn);
                found=1;
            } else if(obyt>100000){
                char fn[256]; snprintf(fn,sizeof fn,"rootfs_out_%ld.bin",off);
                FILE*o=fopen(fn,"wb"); fwrite(out,1,obyt,o); fclose(o);
                printf("   ** large output -> wrote %s\n",fn);
                found=1;
            }
        }
    }
    if(!found)printf("no LZO1X stream found up to offset 0x%lx\n",maxoff);
    return 0;
}
