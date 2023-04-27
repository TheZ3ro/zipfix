# This files contains code from https://github.com/ejrh/ejrh/blob/master/utils/zipfix.py

import zipfile
import struct
import sys
import os

data_descriptor = False
skip_size_check = False

structDataDescriptor = b"<4sL2L"
stringDataDescriptor = b"PK\x07\x08"
sizeDataDescriptor = struct.calcsize(structDataDescriptor)

_DD_SIGNATURE = 0
_DD_CRC = 1
_DD_COMPRESSED_SIZE = 2
_DD_UNCOMPRESSED_SIZE = 3

def write_data(filename, data):
    if filename.endswith(b'/'):
        os.mkdir(filename)
    else:
        with open(filename, 'wb') as f:
            f.write(data)

def fdescriptor_reader(file, initial_offset=zipfile.sizeFileHeader):
    offset = initial_offset
    file.seek(offset)
    while True:
        temp = file.read(1024)
        if len(temp) < 1024:
            print('Found end of file. Some entries missed.')
            return None

        parts = temp.split(stringDataDescriptor)
        if len(parts) > 1:
            offset += len(parts[0])
            break
        else:
            offset += 1024
    file.seek(offset)

    ddescriptor = file.read(sizeDataDescriptor)
    if len(ddescriptor) < sizeDataDescriptor:
        print('Found end of file. Some entries missed.')
        return None
    
    ddescriptor = struct.unpack(structDataDescriptor, ddescriptor)
    if ddescriptor[_DD_SIGNATURE] != stringDataDescriptor:
        print('Error reading data descriptor.')
        return None

    file.seek(initial_offset)
    return ddescriptor


def main(filename):
    print('Reading %s Central Directory' % filename)

    # Get info from ZIP Central Directory
    with zipfile.ZipFile(filename, 'r') as myzip:
        files = myzip.namelist()
        print('Found %d file(s) from Central Directory:' % (len(files)))
        print('- ' + '\n- '.join(files))

    print('Reading %s ZIP entry manually' % filename)
    with open(filename, 'rb') as f:
        while True:
            # Read and parse a file header
            fheader = f.read(zipfile.sizeFileHeader)
            if len(fheader) < zipfile.sizeFileHeader:
                print('Found end of file. Some entries missed.')
                break
        
            fheader = struct.unpack(zipfile.structFileHeader, fheader)
            if fheader[zipfile._FH_SIGNATURE] == zipfile.stringCentralDir:
                print('Found start of central directory. All entries processed.')
                break

            if fheader[zipfile._FH_SIGNATURE] != zipfile.stringFileHeader:
                raise Exception('Size mismatch! File Header expected, got "%s"' % (fheader[zipfile._FH_SIGNATURE]))

            if fheader[zipfile._FH_GENERAL_PURPOSE_FLAG_BITS] & 0x8:
                data_descriptor = True
        
            fname = f.read(fheader[zipfile._FH_FILENAME_LENGTH])
            if fheader[zipfile._FH_EXTRA_FIELD_LENGTH]:
                f.read(fheader[zipfile._FH_EXTRA_FIELD_LENGTH])
            print('Found %s' % fname.decode())

            # Fake a zipinfo record
            zi = zipfile.ZipInfo()
            zi.filename = fname
            zi.compress_size = fheader[zipfile._FH_COMPRESSED_SIZE]
            zi.compress_type = fheader[zipfile._FH_COMPRESSION_METHOD]
            zi.flag_bits = fheader[zipfile._FH_GENERAL_PURPOSE_FLAG_BITS]

            if data_descriptor:
                # Compress size is zero
                # Get the real sizes with data descriptor
                ddescriptor = fdescriptor_reader(f, f.tell())
                if ddescriptor is None:
                    break
                zi.compress_size = ddescriptor[_DD_COMPRESSED_SIZE]
                zi.file_size = ddescriptor[_DD_UNCOMPRESSED_SIZE]
                zi.CRC = ddescriptor[_DD_CRC]

            # Read the file contents
            zef = zipfile.ZipExtFile(f, 'rb', zi)
            data = zef.read()
        
            # Sanity checks
            if len(data) != zi.file_size:
                raise Exception("Unzipped data doesn't match expected size! %d != %d, in %s" % (len(data), zi.file_size, fname))
            calc_crc = zipfile.crc32(data) & 0xffffffff
            if calc_crc != zi.CRC:
                raise Exception('CRC mismatch! %d != %d, in %s' % (calc_crc, zi.CRC, fname))
        
            # Write the file
            write_data(fname, data)

            if data_descriptor:
                # Skip dataDescriptor before reading the next file
                f.seek(f.tell() + sizeDataDescriptor)

    f.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python zipfix.py <filename>")
    else:
        main(sys.argv[1])
