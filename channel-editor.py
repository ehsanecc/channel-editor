# ChannelEditor v0.1 by Ehsan Varasteh 2022
# Website: https://zaxis.ir/
# #########################################

# Feel free to change this source code by your needs!

from sys import argv
import binascii, io, math, struct, zlib
from io import BytesIO

# GUI
from tkinter import *
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog

# global vars
binEnding = None
chnBody = None
channelList = []
currentOpenfilename = None

def gui_manipulate_lb(LB:Listbox, cmd:str):
    if cmd == 'U': # move up
        s = LB.curselection()
        if s:
            for i in s:
                if i > 0:
                    b = LB.get(i, i)
                    bC = LB.itemconfig(i)
                    LB.delete(i)
                    LB.insert(i-1, b[0])
                    LB.itemconfig(i-1, {'bg':bC['background'][-1:][0]})
                    LB.selection_set(i-1)
    elif cmd == 'D': # move down
        s = LB.curselection()
        if s:
            for i in reversed(s):
                if i < LB.size()-1:
                    b = LB.get(i, i)
                    bC = LB.itemconfig(i)
                    LB.delete(i)
                    LB.insert(i+1, b[0])
                    LB.itemconfig(i+1, {'bg':bC['background'][-1:][0]})
                    LB.selection_set(i+1)
    elif cmd == 'R': # remove
        s = LB.curselection()
        if s:
            for i in s:
                LB.delete(LB.curselection()[0])

def read_channel(fileHandler):
    global binEnding

    packPos = fileHandler.tell()
    channelData = {}
    channelData['magic'] = fileHandler.read(4)
    if len(channelData['magic']) != 4 or channelData['magic'] != b'UU\0\0':
        return None
    channelData['nameLength'] = struct.unpack('B', fileHandler.read(1))[0]
    channelData['d0'] = binascii.hexlify(fileHandler.read(3), ' ') # skip these
    channelData['P'] = f"{struct.unpack('H', fileHandler.read(2))[0]:04}"
    channelData['V'] = f"{struct.unpack('H', fileHandler.read(2))[0]:04}"
    channelData['d1'] = binascii.hexlify(fileHandler.read(31), ' ') # skip these
    # x = 3 + (n*4)         =>      n = (x - 3)/4
    if channelData['nameLength'] in range(3,255,4): # ok
        r = channelData['nameLength']
    else:
        r = channelData['nameLength']
        n = math.floor((r-3)/4)
        if abs(r - ((n * 4) + 3)) >= abs(r-(((n+1) * 4) + 3)):
            r = ((n+1) * 4) + 3
        else:
            r = (n * 4) + 3

    channelData['channelName'] = fileHandler.read(r).ljust(30) #.decode('utf-8')
    channelData['A'] = struct.unpack('H', fileHandler.read(2))[0]
    channelData['flags'] = struct.unpack('H', fileHandler.read(2))[0]
    channelData['d2'] = b''
    
    buffer = fileHandler.read(4)
    while len(buffer) == 4 and buffer != b'UU\0\0':
        buffer = fileHandler.read(4)
        if len(buffer) == 4 and buffer != b'UU\0\0':
            channelData['d2'] += buffer
        if len(buffer) == 4 and buffer == b'\x45\x00\x29\x05':
            break
    if (len(buffer) < 4):
        return None
    channelData['d2'] = binascii.hexlify(channelData['d2'], ' ')
    fileHandler.seek(-4, io.SEEK_CUR)
    channelData['scramble'] = True if channelData['flags'] & (1<<8) else False
    channelData['length'] = fileHandler.tell() - packPos
    fileHandler.seek(-1 * channelData['length'], io.SEEK_CUR)
    channelData['rawData'] = fileHandler.read(channelData['length']) # read back all!
    if buffer == b'\x45\x00\x29\x05':
        binEnding = fileHandler.read() # read till the end
    if channelData['magic'] != b'UU\0\0':
        exit()
    
    return channelData

def read_chn(fileHandler):
    fileHandler.seek(0, io.SEEK_SET) # first of file
    chnBody = {}
    (chnBody['magic'], chnBody['version'], chnBody['ExtractedSize'],
        chnBody['TVChannelCount'], chnBody['RadioChannelCount'],
        chnBody['Unknown'], chnBody['ZippedDataLen']) = struct.unpack('<4s24sQHH16sQ', fileHandler.read(64))
    if chnBody['magic'] == b'CHN\0':
        chnBody['UnzippedChannels'] = zlib.decompress(fileHandler.read(chnBody['ZippedDataLen']))
    else:
        return None
    
    return chnBody

def donothing():
    pass

def open_file(fileName):
    global listboxChannels, currentOpenfilename, channelList, chnBody

    with open(fileName, 'rb') as inputFile:
        listboxChannels.delete(0, listboxChannels.size())
        magic = inputFile.read(4)
        if magic == b'CHN\0':
            print('CHN file detected.\nReading file ... ', end='')
            chnBody = read_chn(inputFile)
            inputFile.close()
            if chnBody:
                print('DONE\n### INFO: \n Version: %s\n TV Channel Count: %d\n Radio Channel Count: %d\n\n' % 
                    (chnBody['version'], chnBody['TVChannelCount'], chnBody['RadioChannelCount']))
                inputFile = BytesIO(chnBody['UnzippedChannels'])

        channelList = []
        for i in range(1, chnBody['TVChannelCount']+10):
            channelData = read_channel(inputFile)
            if channelData == None:
                i -= 1
                break
            channelList.append(channelData)
            listboxChannels.insert(i, f"{i:04}:{channelData['channelName'].decode('utf8', errors='ignore').strip()} {' $$$' if channelData['scramble'] else ''}")
            if channelData['scramble']:
                listboxChannels.itemconfig(i-1, {'bg':'gold'})

        if i > 1:
            currentOpenfilename = fileName
            messagebox.showinfo("Read Success", f"Report:\n\nVersion: {chnBody['version'][:-2].decode('ascii')}\n"\
                f"TV Channel Count: {chnBody['TVChannelCount']}\n"\
                f"Radio Channel Count: {chnBody['RadioChannelCount']}\n\n"\
                f"{i} channels read successfully!")

def save_file(filename):
    global listboxChannels, channelList, binEnding, chnBody

    with open(filename, 'wb') as outputFile:
        channelList_bin = b''
        for i in range(0, listboxChannels.size()):
            channel = listboxChannels.get(i, i)[0]
            channelIndex = int(channel.split(':')[0]) -1
            channelList_bin += channelList[channelIndex]['rawData']
        channelList_bin += binEnding

        channelList_zip = zlib.compress(channelList_bin)
        outputFile.write(struct.pack('<4s24sQHH16sQ', chnBody['magic'], chnBody['version'], len(channelList_bin) +24,
            listboxChannels.size(), chnBody['RadioChannelCount'],
            chnBody['Unknown'], len(channelList_zip)))

        outputFile.write(channelList_zip)

def menuOpen():
    fo = filedialog.askopenfilename()
    if fo:
        open_file(fo)

def menuSaveas():
    fo = filedialog.asksaveasfilename()
    if fo:
        save_file(fo)

def menuSave():
    global currentOpenfilename
    save_file(currentOpenfilename)

# initializing gui
top = Tk()
top.title('ChannelEditor v0.1 by Ehsan Varasteh 2022')
top.resizable(0, 0)

topFrame = Frame(top)
scrollBar = Scrollbar(topFrame)
listboxChannels = Listbox(topFrame, width=40, height=30, yscrollcommand=scrollBar.set, selectmode='extended', font='"Courier New" 12 bold')
scrollBar.config(command=listboxChannels.yview)
scrollBar.pack(side=RIGHT, fill=BOTH)

listboxChannels.pack()
topFrame.pack(side=LEFT, padx=2.5, pady=2.5)

bottomFrame = Frame(top)
Button(bottomFrame, text='Move Up', command=lambda: gui_manipulate_lb(listboxChannels, 'U'), width=12).pack(side=TOP, pady=2.5)
Button(bottomFrame, text='Move Down', command=lambda: gui_manipulate_lb(listboxChannels, 'D'), width=12).pack(side=TOP, pady=2.5)
Button(bottomFrame, text='Delete', command=lambda: gui_manipulate_lb(listboxChannels, 'R'), width=12).pack(side=TOP, pady=2.5)
Button(bottomFrame, text='(De)Select All', command=lambda: listboxChannels.select_clear(0,listboxChannels.size()) if listboxChannels.select_includes(0) else listboxChannels.select_set(0,listboxChannels.size()), 
    width=12).pack(side=TOP, pady=2.5)
bottomFrame.pack(side=TOP, padx=5)

menubar = Menu(top)
filemenu = Menu(menubar, tearoff=0)
filemenu.add_command(label="Open", command=menuOpen)
filemenu.add_command(label="Save", command=menuSave)
filemenu.add_command(label="Save as ...", command=menuSaveas)
filemenu.add_separator()
filemenu.add_command(label="Exit", command=lambda:exit())
menubar.add_cascade(label="File", menu=filemenu)

helpmenu = Menu(menubar, tearoff=0)
helpmenu.add_command(label="About...", command=lambda:messagebox.showinfo('About', 'Created by Ehsan Varasteh 2022\nWebsite: https://zaxis.ir/'))
menubar.add_cascade(label="Help", menu=helpmenu)
top.config(menu=menubar)

if len(argv) > 1:
    open_file(argv[1])

top.mainloop()

