#include "compression.h"

void Compression::compressFile(std::string path)
{
    /*
    int startTime=QDateTime::currentMSecsSinceEpoch();
    FILE *infile = fopen(path.c_str(), "rb");
    gzFile outfile = gzopen((path+".sav").c_str(), "wb");
    char inbuffer[512];
    int num_read = 0;
    while ((num_read = fread(inbuffer, 1, sizeof(inbuffer), infile)) > 0) {
        gzwrite(outfile, inbuffer, num_read);
    }
    fclose(infile);
    gzclose(outfile);
    remove(path.c_str());
    int endTime=QDateTime::currentMSecsSinceEpoch()-startTime;
    qDebug()<<"Compressed"<<path.c_str()<<"in"<<endTime<<"ms\n";
    */
}


void Compression::decompressFile(std::string path)
{
    /*
    int startTime=QDateTime::currentMSecsSinceEpoch();
    gzFile infile = gzopen(path.c_str(), "rb");
    FILE *outfile = fopen(path.substr(0,path.find(".sav")).c_str(), "wb");
    char buffer[512];
    int num_read = 0;
    while ((num_read = gzread(infile, buffer, sizeof(buffer))) > 0) {
        fwrite(buffer, 1, num_read, outfile);
    }
    gzclose(infile);
    fclose(outfile);
    int endTime=QDateTime::currentMSecsSinceEpoch()-startTime;
    qDebug()<<"Decompressed"<<path.c_str()<<"in"<<endTime<<"ms\n";
    */
}
