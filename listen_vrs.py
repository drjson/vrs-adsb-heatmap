#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
from time import sleep
from math import floor
import json
import argparse
import logging

ip = "127.0.0.1"
port = 33001

# Upper Right = xx.xxxxx, yy.yyyyyy
upper_right = (30.00000 , -30.000000)
# Lower Left = xx.xxxxxx, yy.yyyyyy
lower_left = (40.00000, -40.000000)
# Grid = 1000x1000

class Grid(object):

    # grid is anchored at ll location
    # upper right, lower left, size
    def __init__(self, ur, ll, sz=500):
        self.delta_lat = ur[0] - ll[0];
        self.delta_lon = ur[1] - ll[1];
        self.step_lat = self.delta_lat/sz;
        self.step_lon = self.delta_lon/sz;
        self.ur = ur;
        self.ll = ll;
        self.sz = sz;

        self.grid = [ [0]*sz for _ in range(sz) ];


    def place(self, lat, lon):
        if(lat > self.ur[0] or lat < self.ll[0]):
            return
        if(lon > self.ur[1] or lon < self.ll[1]):
            return

        x = floor( (lon - self.ll[1])/self.step_lon )
        y = floor( (lat - self.ll[0])/self.step_lat )

        self.grid[x][y] += 1;

    def __str__(self):
        ret = ""
        for y in range(self.sz-1,0,-1):
            for x in range(self.sz):
                ret += "{0:3d} ".format(self.grid[x][y]);

            ret+= "\n";

        return ret

    # TODO: Change to actual JSON unstead of generating JavaScript
    def saveJson(self, filename):
        with open(filename, 'w') as of:
            of.write("function getHeatmap() {\n")
            of.write("var HeatmapData = [\n")
            for y in range(self.sz-1,0,-1):
                for x in range(self.sz):
                    if (self.grid[x][y] > 0):
                        midpoint = (self.ll[0]+y*self.step_lat+self.step_lat/2,
                                    self.ll[1]+x*self.step_lon+self.step_lon/2)
                        line = "  {{location: new google.maps.LatLng({}, {}), weight: {}}},\n".format(
                                midpoint[0], midpoint[1], self.grid[x][y])
                        of.write(line)

            of.write("];\n")
            of.write("return HeatmapData;\n")
            of.write("}\n")


    __repr__ = __str__

async def parse_basestation(ip, port, loop, grid):
    first = 1
    while True:
        if not first:
            logging.warning("Lost connection, attempting reconnect in 30 seconds...")
            await windows_sleep(30)

        first = 0

        try:
            reader, writer = await asyncio.open_connection(ip, port, loop=loop)
        except ConnectionRefusedError:
            logging.warning("Connection Refused: {}:{}".format(ip,port))
            continue
        while True:
            try:
                line = await reader.readuntil(b'\r\n')
            except asyncio.streams.IncompleteReadError:
                return
            fields = line.decode().split(',')
            if fields[0] in ['MSG', 'MLAT']:
                if fields[1] in ['3', '4']:
                    #print("[{8} {9}] {4} {10} Lat:{14} Long:{15} Alt:{11}".format(*fields))
                    if(fields[14] != "" and fields[15] != ""):
                        grid.place(float(fields[14]), float(fields[15]))


async def windows_sleep(seconds):
    # Workaround issue Python#23057
    for i in range(seconds*10):
        sleep(0.1)


async def save_grid(grid, filename, seconds=3600):
    while True:
        await asyncio.sleep(seconds);
        logging.info("Writing {}".format(filename))
        grid.saveJson(filename);


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("filename")
    parser.add_argument("-s", "--seconds", action="store", default=3600, type=int)
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p',
                        level=logging.INFO)


    loop = asyncio.get_event_loop()

    grid = Grid(upper_right, lower_left)

    try:
        print("Ctrl-C to Stop")
        while True:
            loop.run_until_complete(asyncio.gather(
                parse_basestation(ip, port, loop, grid),
                save_grid(grid, args.filename, args.seconds)))

    except KeyboardInterrupt:
        logging.warning("Ctrl-C Caught!")
        pass
    finally:
        loop.close()
        grid.saveJson(args.filename)


