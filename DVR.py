import time
import sys
import os
import threading
from socket import *
import math

SUSPEND_AFTER_TIMEOUT = 3.0 #timeout has happened. This time is waited until bellman-ford is executed.

class Path:
    def __init__(self, distance, nextHop):
        self.distance = distance
        self.nextHop = nextHop

    def equals(self, path2):  #to check if two paths are equal
        return self.distance == path2.distance and self.nextHop == path2.nextHop  #


class Neighbour:
    def __init__(self, linkCost, port, timeout):
        self.linkCost = linkCost
        self.port = port
        self.timeout = timeout
        self.paths = dict()

r_ID = str()
r_port = int()
r_fileName = str()
r_neighbours = dict()
r_routes = dict()

lock = threading.Lock()

def create_pkt(dest_id, sendLinkCost):
    distanceVector = str(r_ID)  #distance vector packet e.g. A  B  4.5 (paths)

    if sendLinkCost:  #if you wanna send
        distanceVector += ' ' + str(r_neighbours[dest_id].linkCost)  #link cost of that router
    distanceVector += '\n'

    for id, path in r_routes.items():
        if path.nextHop == dest_id:  #split horizon
            distanceVector += str(id) + " " + str(math.inf) + '\n'
        else:
            distanceVector += str(id) + " " + str(path.distance) + '\n'  #neigbor d

    return bytes(distanceVector, 'utf-8')


def sendDV(sendLinkCost):
    sendSocket = socket(AF_INET, SOCK_DGRAM)
    lock.acquire()
    for id, neighbour in r_neighbours.items():  #senidng to every neigbor
        sendSocket.sendto(create_pkt(id, sendLinkCost), ('localhost', neighbour.port))
    lock.release()
    sendSocket.close()

def printTable():
    string = '\t'

    for id in sorted(r_routes.keys()):  #router IDs
        string += '\t' + id
    print(string)

    string = r_ID + '\t'
    for id in sorted(r_routes.keys()):  #distance (specific to paths)
        string += '\t' + str("%.1f" % r_routes[id].distance)
    print(string)

    for id in sorted(r_neighbours.keys()):  #neigbors ka distance vector
        string = id+'\t'+str(r_neighbours[id].linkCost)
        for key2 in sorted(r_neighbours[id].paths.keys()):
            string += '\t' + str("%.1f" % r_neighbours[id].paths[key2].distance)
        print(string)
    print('')

def timeOutCheck():
    while 1:
        time.sleep(1)  #after every 1 second
        for id, neighbour in r_neighbours.items():  #going through every neighbor
            s = socket(AF_INET, SOCK_DGRAM)  #UDP socket
            try:
                s.bind(('localhost', neighbour.port))  #neighbor port reserved
                #router is dead:
                s.close() #port closed
                if r_neighbours[id].linkCost != math.inf:  #if timeout not catered before
                    lock.acquire()

                    r_routes[id].distance = math.inf  #infinity
                    neighbour.linkCost = math.inf  #infinty
                    neighbour.timeout = time.time()  #current time
                    for key2, item2 in r_routes.items():  #all paths throughout it set to infinity
                        if item2.nextHop == id:
                            item2.distance = math.inf

                    lock.release()
                    sendDV(False)  #updated distance vector
                    threading.Timer(SUSPEND_AFTER_TIMEOUT, target=bellManFord).start()  #bellman ford executed after that time
            except:
                pass  #router is alive

def listen():
    listenSocket = socket(AF_INET, SOCK_DGRAM)
    listenSocket.bind(('localhost', r_port))
    while 1:
        message, socketAddress = listenSocket.recvfrom(2048)

        lines = str(message)[2:len(str(message))-1].split('\\n')
        firstLine = lines[0].split()
        source = firstLine[0]

        r_neighbours[source].timeout = -1.0

        if len(firstLine) > 1:
            r_neighbours[source].linkCost = float(firstLine[1])
            r_neighbours[source].timeout = -1

        lock.acquire()
        for i in range(1, len(lines)):
            if lines[i] == '':
                continue
            tokens = lines[i].split()
            newPath = Path(float(tokens[1]),'direct')
            if tokens[0] not in r_neighbours[source].paths:
                newNode(tokens[0])
            if not r_neighbours[source].paths[tokens[0]].equals(newPath):
                r_neighbours[source].paths[tokens[0]] = newPath
        threading.Thread(target=bellManFord).start()
        lock.release()


def newNode(name):  #new neighbors ki baat
    global r_neighbours
    p = Path(math.inf, 'direct')  #infifinty initialize
    r_routes[name] = p
    for id, neighbour in r_neighbours.items():
        neighbour.paths[name] = p #inifinty


def bellManFord():
    global r_routes

    isChanged = False

    lock.acquire()
    for id, route in r_routes.items():
        m_list = list()
        if id == r_ID:  #0
            continue
        if id in r_neighbours:
            if time.time() > r_neighbours[id].timeout and time.time() < r_neighbours[id].timeout + SUSPEND_AFTER_TIMEOUT:
                r_routes[id] = Path(math.inf, 'direct')
                continue
            else:
                m_list.append(Path(r_neighbours[id].linkCost, 'direct'))

        for id2, neighbour in r_neighbours.items():
            p = Path(r_neighbours[id2].linkCost + neighbour.paths[id].distance, id2)
            m_list.append(p)
        m_list.append(p)
        m = min(m_list, key = lambda x: x.distance)  #main line nigga
        if not r_routes[id].equals(Path(m.distance,m.nextHop)):
            r_routes[id] = Path(m.distance,m.nextHop)
            isChanged = True

    lock.release()
    if isChanged:
        sendDV(False)


def menu():
    option = 0
    while(1):
        print('\n****I AM ROUTER ' + r_ID + '****\n')

        option = int(input('1: Display Costs.\n2: Display distance vector table.\n3: Edit link costs\n4: Quit\nYour choice: '))
        if option == 1:
            print('Destination\tNext Hop\tDistance')
            for id, route in sorted(r_routes.items()):
                if id != r_ID:
                    print('     ' + id + '\t\t' + route.nextHop + '\t\t' + str("%.1f" % route.distance))
        elif option == 2:
            printTable()
        elif option == 3:
            string = 'Neighbours:'
            for id in sorted(r_neighbours.keys()):
                string += ' ' + id
            print(string)
            toEdit = input('Enter which link to edit: ')
            newDistance = float(input('Enter new distance for ' + toEdit + ': '))
            r_neighbours[toEdit].linkCost = newDistance

            sendSocket = socket(AF_INET, SOCK_DGRAM)
            lock.acquire()
            sendSocket.sendto(create_pkt(toEdit, True), ('localhost', r_neighbours[toEdit].port))
            lock.release()
            sendSocket.close()

            threading.Thread(target=bellManFord).start()

        elif option == 4:
            os._exit(-1)

if __name__ == '__main__':  #starting point
    try:
        r_ID = sys.argv[1]
        r_port = int(sys.argv[2])
        r_fileName = sys.argv[3]
    except ValueError or IndexError:
        print('Incorrect command-line arguments.\nDVR.py <ID> <port> <filename>')
        exit(0)

    print("Router "+r_ID)

    r_routes[r_ID] = Path(0, 'direct')

    file = open(r_fileName)
    lines = file.readlines()
    for i in range(1, len(lines)):
        tokens = lines[i].split()
        r_neighbours[tokens[0]] = Neighbour(float(tokens[1]), int(tokens[2]), -1)
        r_routes[tokens[0]] = Path(float(tokens[1]), 'direct')
    for id, neighbour in r_neighbours.items():  #new nodes wala kaam
        p = Path(math.inf, 'direct')
        for id2, neighbour2 in r_neighbours.items():
            neighbour.paths[id2] = p
        neighbour.paths[r_ID] = Path(0, 'direct')

    threading.Thread(target=sendDV, kwargs={'sendLinkCost': True}).start()  #temporary thread for seding DV

    threading.Thread(target=listen).start()
    threading.Thread(target=menu).start()
    #time.sleep(5)
    threading.Thread(target=timeOutCheck).start()
