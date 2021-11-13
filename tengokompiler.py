# By arthur
# oh and also bob

import math
from gameData import *

currGame = None

#x----------------------------------------------------------Decompilation-----------------------------------------------X


# Get value of a little endian word from the sequence of bytes
def getWord(wordBytes):
    return wordBytes[3]*16777216 + wordBytes[2]*65536 + wordBytes[1]*256 + wordBytes[0]


# Format a function argument depending on its size
def formatArg(argument):
    if argument < 0x01000000:
        return str(argument)
    else:
        return "0x%08x" % argument 


# 03 funcs that are documented
def get03FuncCmd(command, gbaBytes):
    function = getWord(command[4:8])
    argument = getWord(command[8:12])
    
    if function == 0x080179f5: # Universal cue
        return "universalCue %d" % argument
    elif function == 0x0800bdf9: # Tempo
        return "setTempo %d" % argument
    elif function == 0x080173c5: # Enable inputs
        return "inputsEnabled %s" % ("TRUE" if argument else "FALSE")
    elif function == 0x0801747d: # skip practice alternative?
        if argument == 0: # todo: figure out the fucking deal with this related to the similar 04 command
            return "skipPractice03 NULL // disable"
        else:
            subAddr = getWord(gbaBytes[argument-0x08000004 : argument-0x08000000])
            subName = getSubName(subAddr)
            decompileQueue[subAddr] = subName
            return "skipPractice03 0x%08x, %s" % (argument, subName)        
    elif function == 0x08017381: # Gfx func part 1
        return "gfx1 %s" % argument
    
    return "run func_%08x, %s" % (function-1, formatArg(argument))


# Create formatted graphics function using the game data
def getGfxFunc(bank, funcID, arg):
    if bank in gameBanks.keys():
        gameGfxFunc = gameBanks[bank][1][funcID]
        if gameGfxFunc[1] == GFX_FUNC_NO_ARG: # Function takes no arguments
            return "%s" % gameGfxFunc[0]
        elif gameGfxFunc[1] == GFX_FUNC_NUM_ARG: # Function takes a number as an argument
            return "%s %d" % (gameGfxFunc[0], arg)
        elif gameGfxFunc[1] == GFX_FUNC_BEAT_VALUE: # Function takes a time in beats as an argument
            return "%s %d // %g beat%s" % (gameGfxFunc[0], arg, arg/24.0, "s" if arg != 24 else "")
        elif gameGfxFunc[1] == GFX_FUNC_IDS: # Function takes indices as an argument
            return "%s %s" % (gameGfxFunc[0], gameGfxFunc[2][arg])
        elif gameGfxFunc[1] == GFX_FUNC_POINTER: # Function takes a pointer as an argument
            return "%s %s" % (gameGfxFunc[0], "NULL" if arg == 0 else "0x%08x" % arg)
        elif gameGfxFunc[1] == GFX_FUNC_BOOLEAN: # Function takes a boolean as an argument
            return gameGfxFunc[0] + (" FALSE" if arg == 0 else " TRUE")
    
    return "gfxFunc 0x%08x, %d, %s" % (bank, funcID, formatArg(arg))


# Todo: this is disgusting, just keep one global mapping of rom addresses and subs
decompileQueue = {} # Subs that need to be decompiled - key: address, value: sub name
decompiled = {} # Subs that have already been decompiled - key: address, value: [list of commands, rom address of end, sub name]
curSub = 0 # Keep track of what number to assign subs

def getSubName(address):
    global curSub
    
    if address in hardcodedSubs.keys():
        subName = hardcodedSubs[address]
    elif address in decompileQueue.keys():
        subName = decompileQueue[address]
    elif address in decompiled.keys():
        subName = decompiled[address][2]
    else:
        # Generate new sub name
        subName = "sub_%02d" % curSub
        curSub += 1  
    return subName

# Decompile a list of bytes into script commands
def decompileCommands(gbaBytes, romOffset):
    global decompileQueue, decompiled

    endOfCommands = False
    commandstorage = []
    indent = 0

    while not endOfCommands:
        # Fetch command bytes
        command = gbaBytes[romOffset : romOffset + 12]
        romOffset += 12
        deindent = False

        commandID = command[0]
        if "-n" not in selection: 
            # TODO add more functions here
            # Rest (00)
            if commandID == 0x00:
                argument = command[8]
                commandStr = "rest %d // %g beat%s" % (argument, argument/24.0, "s" if argument != 24 else "")
                
            # End statement (01)
            elif commandID == 0x1:
                commandStr = "end"
                if indent <= 0:
                    endOfCommands = True            

            # ASM with 1 argument (03)
            elif commandID == 0x03:
                commandStr = get03FuncCmd(command, gbaBytes)

            # ASM with 2 arguments (04)
            # This should definitely be moved into a function like 03 - todo
            elif commandID == 0x04:
                function = getWord(command[4:8])
                argument1 = getWord(command[8:12])
                argument2 = command[1]
                # Second half of a graphics function
                if function == 0x0801738d and isGfxFunc:
                    commandStr = getGfxFunc(argument1, argument2, int(commandstorage[-1][5:]))
                    # Remove first half
                    del commandstorage[-1]
                # Remix transition
                elif function == 0x08017189:
                    if argument1 in gameBanks.keys():
                        currGame = gameBanks[argument1]
                        commandStr = "\nloadGame %s, %d" % (currGame[0], argument2)
                    else:
                        commandStr = "\nloadGame 0x%08x, %d" % (argument1, argument2)
                # Beat animation
                elif function == 0x08017349: 
                    if argument1 == 0 and argument2 == 0:
                        commandStr = "beatAnim"
                    elif argument2 == 2: # not TOO sure on this
                        if argument1 == 0:
                            commandStr = "skipPractice04 NULL // disable"
                        else:
                            subAddr = getWord(gbaBytes[argument1-0x08000004 : argument1-0x08000000])
                            subName = getSubName(subAddr)
                            decompileQueue[subAddr] = subName
                            commandStr = "skipPractice04 0x%08x, %s" % (argument1, subName)
                    else: # todo until i figure out what this is
                        commandStr = "run func_%08x, %s, %d" % (function-1, formatArg(argument1), argument2)
                # other
                else:
                    commandStr = "run func_%08x, %s, %d" % (function-1, formatArg(argument1), argument2)

            # Jump statement (0D)
            elif commandID == 0xD:
                address = getWord(command[4:8])
                # Try to find sub name if it already exists
                subName = getSubName(address)
                commandStr = "jump %s" % subName
                # Queue the sub for decompilation. If it has already been decompiled it will be skipped later
                decompileQueue[address] = subName
            
            
            # ewwwww don't use this for gotos.......
            # Goto statement (0F)
            elif commandID == 0xF:
                address = getWord(command[4:8])
                # Try to find sub name if it already exists
                subName = getSubName(address)
                commandStr = "goto %s" % subName
                # Queue the sub for decompilation. If it has already been decompiled it will be skipped later
                decompileQueue[address] = subName
                if indent <= 0:
                    endOfCommands = True                  

            # Return statement (0E)
            elif commandID == 0xE:
                commandStr = "return"
                if indent <= 0:
                    endOfCommands = True

            # If statement (12)
            elif commandID == 0x12:
                offset = getWord(command[4:8])
                argument = formatArg(getWord(command[8:12]))
                commandStr = "ifeq D_%08x, %s" % (offset, argument)
                indent += 1
                deindent = True

            # Else statement (14)
            elif commandID == 0x14:
                commandStr = "else"
                deindent = True

            # endif statement (15)
            elif commandID == 0x15:
                commandStr = "endif"
                indent -= 1
                
            # Switch statement (1A)
            elif commandID == 0x1A and int(command[1]) in (0,3): # temp while i figure out wtf the other values are
                argument = getWord(command[8:12])
                if int(command[1]) == 0:
                    commandStr = "switchVar D_%08x" % (argument)
                elif int(command[1]) == 3:
                    commandStr = "switchFunc func_%08x" % (argument-1)
                indent += 1
                deindent = True
                
            # End switch statement (1B)
            elif commandID == 0x1B:
                commandStr = "endswitch"
                indent -= 1            
                    
            # Case statement (1C)
            elif commandID == 0x1C:
                argument = formatArg(getWord(command[8:12]))
                commandStr = "case %s" % (argument)
                deindent = True
                
            # Break switch statement (1D)
            elif commandID == 0x1D:
                commandStr = "break"
                
            # Unknown, some kind of alternative if statement? (21)
            elif commandID == 0x21:
                arg1 = getWord(command[4:8])
                arg2 = getWord(command[8:12])
                commandStr = "cmd21 %d, %d, %d" % (command[1], arg1, arg2)
                indent += 1
                deindent = True            

            # Play midi (28)
            elif commandID == 0x28:
                argument = getWord(command[4:8])
                midi = getWord(command[8:12])
                midi = gameMidis[midi] if midi in gameMidis.keys() else "0x%08x" % midi
                commandStr = "playMidi %s, %d" % (midi, argument)

            # Play midi sound effect? (29)
            elif commandID == 0x29:
                midi = getWord(command[8:12])
                midi = gameMidis[midi] if midi in gameMidis.keys() else "0x%08x" % midi
                commandStr = "playMidiSfx %s" % midi

            # Set pitch (3E)
            elif commandID == 0x3E:
                argument = formatArg(getWord(command[8:12]))
                commandStr = "setPitch %s" % (argument)
                
            else:
                commandStr = "0x%02x %d, %d, %d, %s, %s" % (commandID, command[1], command[2], command[3], formatArg(getWord(command[4:8])), formatArg(getWord(command[8:12])))             

        isGfxFunc = commandStr[:4] == "gfx1"
        commandStr = "\t"*(indent - 1 if deindent else indent) + commandStr
        commandstorage.append(commandStr)

    # Return all commands and the address of the end of the script
    return [commandstorage, romOffset + 0x08000000]


def decompile(gbaFile, romOffset):
    global decompileQueue, decompiled, curSub
    
    outputLines = ["// Automatically generated by Tengokompiler, rom address 0x%08x" % (romOffset + 0x08000000)]
    
    with open(gbaFile, "rb") as f:
        byteList = f.read()
        f.close()
    
    curSub = 0
    decompileQueue = {romOffset+0x08000000:getSubName(romOffset+0x08000000)}
    decompiled = {}
    decompiledAddresses = [] # Addresses that have been decompiled
    
    while len(decompileQueue) != 0:
        # Decompile the first script in the queue
        address = list(decompileQueue.keys())[0]
        subName = decompileQueue[address]
        del decompileQueue[address]
        
        # Only decompile if it hasn't been done before
        if address not in decompiled.keys():
            decompiled[address] = decompileCommands(byteList, address - 0x08000000)
            decompiled[address].append(subName)
            # decompiled[address] is a list of 3 elements: the decompiled commands, the rom address of the end of the script, and the name of the sub
            decompiledAddresses.append(address)
    
    # Sort decompiled scripts by ROM address
    decompiledAddresses.sort()
    
    # Go through the scripts in order and add them to the final output
    for i in range(len(decompiledAddresses)):
        outputLines += ["",""]
        
        # Check if the script immediately follows the previous one, so we can skip the address setting
        if i == 0 or decompiled[decompiledAddresses[i-1]][1] != decompiledAddresses[i] or True:
            outputLines += [".setAddress 0x%x" % (decompiledAddresses[i] - 0x08000000),""]
            
        # Check if the sub is named and needs a label
        if decompiled[decompiledAddresses[i]][2] is not None:
            outputLines += [".label %s" % (decompiled[decompiledAddresses[i]][2]),""]
            
        outputLines += decompiled[decompiledAddresses[i]][0]

    return "\n".join(outputLines) + "\n"


#x----------------------------------------------------------Compilation-----------------------------------------------X


# Convert a single integer into little endian bytes
def getBytes(word):
    return [word % 256, math.floor(word % 65536 / 256), math.floor(word % 16777216 / 65536), math.floor(word / 16777216)]


# Interpret a number as either hex or decimal by looking for a 0x
def parseNumber(numStr):
    try: 
        if numStr.startswith("0x"):
            return int(numStr[2:],16)
    except IndexError:
        pass
    if numStr == "NULL" or numStr == "FALSE": return 0
    if numStr == "TRUE": return 1
    return int(numStr)


# Generate an 03 call
def get03FuncBytes(func,arg):
    return [3,0,0,0] + getBytes(func) + getBytes(arg)


# Generate an 04 call
def get04FuncBytes(func,arg1,arg2):
    return [4,arg2,0,0] + getBytes(func) + getBytes(arg1)

labelsNeeded = {}

def linkLabel(sub,addr):
    global labelsNeeded
    
    try: 
        jumpAddr = parseNumber(sub)
    except ValueError: # String used
        jumpAddr = 0 # Set the address to zero to be filled in later
        labelsNeeded[addr] = sub # Remember to fill in this spot with the correct ROM address
    return jumpAddr

# Check if a command is one of the special named functions
def checkSpecialFuncs(cmdType, cmdArgs):
    if cmdType == "universalCue":
        return get03FuncBytes(0x080179f5,parseNumber(cmdArgs[0]))
    elif cmdType == "setTempo":
        return get03FuncBytes(0x0800bdf9,parseNumber(cmdArgs[0]))
    elif cmdType == "inputsEnabled":
        return get03FuncBytes(0x080173c5,parseNumber(cmdArgs[0]))    
    elif cmdType == "loadGame":
        if cmdArgs[0].startswith("GAME"):
            for addr,game in gameBanks.items():
                if game[0] == cmdArgs[0]:
                    gameBank = addr
        else:
            gameBank = parseNumber(cmdArgs[0])
        return get04FuncBytes(0x08017189,gameBank,parseNumber(cmdArgs[1]))
    elif cmdType == "beatAnim":
        return get04FuncBytes(0x08017349,0,0)
    elif cmdType == "skipPractice04":
        addr = parseNumber(cmdArgs[0])
        if addr != 0:
            jumpAddr = linkLabel(cmdArgs[1],addr - 0x08000004)
        return get04FuncBytes(0x08017349,addr,2)
    elif cmdType == "skipPractice03":
        addr = parseNumber(cmdArgs[0])
        if addr != 0:
            jumpAddr = linkLabel(cmdArgs[1],addr - 0x08000004)
        return get03FuncBytes(0x0801747d,addr)        
    return None


# Check if a command is a game-specific graphics function
def checkGfxFuncs(cmdType, cmdArgs):
    for addr,game in gameBanks.items():
        for i in range(len(game[1])):
            gfxFunc = game[1][i]
            if cmdType == gfxFunc[0]:
                # Figure out argument
                if gfxFunc[1] == GFX_FUNC_NO_ARG:
                    gfxFuncArg = 0
                elif gfxFunc[1] == GFX_FUNC_IDS:
                    if type(gfxFunc[2]) is dict:
                        for j, arg in gfxFunc[2].items():
                            if arg == cmdArgs[0]:
                                gfxFuncArg = j
                    else:
                        for j in range(len(gfxFunc[2])):
                            if gfxFunc[2][j] == cmdArgs[0]:
                                gfxFuncArg = j
                else:
                    gfxFuncArg = parseNumber(cmdArgs[0])
                return get03FuncBytes(0x08017381,gfxFuncArg) + get04FuncBytes(0x0801738d,addr,i)
    
    return None


# Find the address for a specified midi
def getMidiAddr(midiArg):   
    for addr, midiName in gameMidis.items():
        if midiName == midiArg:
            return addr
    return parseNumber(midiArg)   


# Compile one script command into bytes
def compileCommand(cmdType, cmdArgs, gbaBytes, romAddress):
    # Rest command 0x00
    if cmdType == "rest":
        cmdBytes = [0,0,0,0,0,0,0,0] + getBytes(parseNumber(cmdArgs[0]))
        
    # End command 0x01
    elif cmdType == "end":
        cmdBytes = [0x1,0,0,0,0,0,0,0,0,0,0,0]    
        
    # Call command 0x03 / 0x04
    elif cmdType == "run":
        func = cmdArgs[0]
        # Check if the function uses a label, and get the real address
        if func.startswith("func_"):
            func = int(func[5:],16)
        else:
            func = parseNumber(func)
        arg1 = parseNumber(cmdArgs[1])
        # Check if the second argument exists, determining the type of command
        try:
            arg2 = parseNumber(cmdArgs[2])
        except IndexError:
            arg2 = None
        # Generate either a 0x03 or 0x04 command
        if arg2 is None:
            cmdBytes = get03FuncBytes(func+1,arg1)
        else:
            cmdBytes = get04FuncBytes(func+1,arg1,arg2)
    
    # Jump command 0x0D
    elif cmdType == "jump":
        jumpAddr = linkLabel(cmdArgs[0],romAddress + 4)
        cmdBytes = [0xD,0,0,0] + getBytes(jumpAddr) + [0,0,0,0]
        
    # Goto command 0x0F
    elif cmdType == "goto":
        jumpAddr = linkLabel(cmdArgs[0],romAddress + 4)
        cmdBytes = [0xF,0,0,0] + getBytes(jumpAddr) + [0,0,0,0]    
        
    # Return command 0x0E
    elif cmdType == "return":
        cmdBytes = [0xE,0,0,0,0,0,0,0,0,0,0,0]
        
    # If command 0x12
    elif cmdType == "ifeq":
        var = cmdArgs[0]
        # Check if the variable uses a label
        if var.startswith("D_"):
            var = int(var[2:],16)
        else:
            var = parseNumber(var)
        arg = parseNumber(cmdArgs[1])
        cmdBytes = [0x12,0,0,0] + getBytes(var) + getBytes(arg)
        
    # Else command 0x14
    elif cmdType == "else":
        cmdBytes = [0x14,0,0,0,0,0,0,0,0,0,0,0]
        
    # End if command 0x15
    elif cmdType == "endif":
        cmdBytes = [0x15,0,0,0,0,0,0,0,0,0,0,0]  
        
    # Unknown, some kind of alternative if statement 0x21
    elif cmdType == "cmd21":
        cmdBytes = [0x21,parseNumber(cmdArgs[0]),0,0] + getBytes(parseNumber(cmdArgs[1])) + getBytes(getMidiAddr(cmdArgs[2]))    
        
    # Play MIDI command 0x28
    elif cmdType == "playMidi":
        cmdBytes = [0x28,0,0,0] + getBytes(parseNumber(cmdArgs[1])) + getBytes(getMidiAddr(cmdArgs[0]))
        
    # Play MIDI as sfx command 0x29
    elif cmdType == "playMidiSfx":
        cmdBytes = [0x29,0,0,0,0,0,0,0] + getBytes(getMidiAddr(cmdArgs[0]))

    # set pitch command 0x3E
    elif cmdType == "setPitch":
        cmdBytes = [0x3E,0,0,0,0,0,0,0] + getBytes(parseNumber(cmdArgs[0]))
        
    elif cmdType[:2] == "0x":
        cmdBytes = [parseNumber(cmdType),parseNumber(cmdArgs[0]),parseNumber(cmdArgs[1]),parseNumber(cmdArgs[2])] + getBytes(parseNumber(cmdArgs[3])) + getBytes(parseNumber(cmdArgs[4]))
        
    else:
        # Check if the command is a special common global function
        encoding = checkSpecialFuncs(cmdType, cmdArgs)
        if encoding is not None:
            cmdBytes = encoding
        else:
            # Check if the command is a game-specific graphics function
            encoding = checkGfxFuncs(cmdType, cmdArgs)
            if encoding is not None:
                cmdBytes = encoding
            else:
                raise NameError("Invalid command: %s" % cmdType)
    
    # Insert the bytes into the ROM at the correct position
    for byte in cmdBytes:
        gbaBytes[romAddress] = byte
        romAddress += 1
        
    # Return how long the command was
    return len(cmdBytes)

# Compile a list of script commands into bytes
def compile(content, gbaBytes):
    global labelsNeeded
    
    commands = content.split("\n")
    
    labelsNeeded = {} # Labels used by jump commands
    labelsSet = {} # Labels defined by .label commands
    romAddress = None # Current rom address of the command being compiled
    
    for command in commands:

        # Kill the indentation and comments brutally
        command = command.split("//")[0].strip()
        if command == "": continue

        # Parse the input and split it into function and arguments
        cmdType = command.split(" ")[0]
        cmdArgs = "".join(command.split(" ")[1:]).split(",")
        
        # Check if the command is a compiler command
        if cmdType[0] == ".":
            if cmdType == ".setAddress":
                romAddress = parseNumber(cmdArgs[0])
            elif cmdType == ".label":
                labelsSet[cmdArgs[0]] = romAddress + 0x08000000
        else: # Command is a script command
            romAddress += compileCommand(cmdType, cmdArgs, gbaBytes, romAddress)
    
    # Resolve all labels by going through and updating the addresses
    for address, label in labelsNeeded.items():
        labelAddr = getBytes(labelsSet[label])
        for addrByte in labelAddr:
            gbaBytes[address] = addrByte
            address += 1


#x----------------------------------------------------------------------MAIN LOOP-----------------------------------------------X

# Little intro text
print("Tengokompiler by Arthurtilly and BobTheNerd10\nINDEV VERSION type 'help' for a list of commands")

# When the user types "help", return all these strings
helpmenu = {
    "help":"\t\tShows a list of commands. Can also use another command as an argument for a more detailed description",
    "decompile":"\tDecompiles manually extracted data",
    "compile":"\t\tCompiles .bs files into .bin files which can then be written to the rom",
    "exit":"\t\tExit the program, thats it. Mainly for use in the command line",
}

# This menu works a lil different because this uses multiple lines
helpdetailed = {
    #"template": [\tmain description, \tusage, \t\targs]
    "help": ["\tShows a list of commands. Can also use another command as an argument for a more detailed description", "\tUsage: help [command]", "\t\t[command]\tThe command you would like help for"],
    "decompile": ["\tDecompiles manually extracted beatscript data to a .bs file", "\tUsage: decompile <inputFile> [-n]", "\t\t<inputFile>\tThe file you would like to decompile", "\t\t-n\t Disable functions for writing as hex"],
    "exit": ["exit\tExits the program. Useful in the command line or with .bat files", "Usage: exit"]
}



# Enter main loop where input is allowed
while True:

    # Get user input
    selection = input().split(" ")

    #x----------------------------------------------------------------------Help Menu-----------------------------------------------X
    # If they typed "help" then...
    if selection[0] == 'help':

        # General Help menu
        if len(selection) == 1:
            print("----TENGOKOMPILER HELP----")

            for command in helpmenu:
                print(command + helpmenu.get(command))
            
            print("--------------------------")


        # Specific Help menu
        else:
        
            # Get the command you want help for
            command = selection[1]


            
            if command in helpdetailed:
                print("--------------------------")
                print(command)
                for desc in helpdetailed.get(command):
                    print(desc)
                print("--------------------------")
            else:
                print(command + " is not a command")
            
                
            #elif selection.find('compile') == 5:
            #    print("compile\t\tcompiles a file, for use on tickflow files\n\tusage: compile <inputFile>\n\t\t\t<inputFile>\tThe file you would like to compile WITHOUT the extension (Must be a .tickflow file)")

        

    #X------------------------------------------------------Decompile Command---------------------------------------------X 
    # decompile untouched.gba 0x9d7330 remix6
    # If the command contains "decompile" at the front   
    elif selection[0] == 'decompile':
        
        # Get 2nd word of command line input and set it to res
        rom = selection[1]
        romOffset = selection[2]
        output = selection[3]

        # Open the specified file as hex and set the hex to the "byteList" variable

        content = decompile(rom,parseNumber(romOffset))

        # Profit (write "content" to new file)
        if not output.endswith(".bs"): output += ".bs"
        with open(output, 'w') as f:
            f.write(content)
            f.close()
        print("Done! Saved to %s" % output)

    #x----------------------------------------------------------------------Compile command-----------------------------------------------X
    # compile remix6.bs baserom.gba
    elif selection[0] == 'compile':

        # Get 2nd word of command line input
        filename = selection[1]
        rom = selection[2]

        # Open the specified file and set the file to the "content" variable
        with open(filename, 'r') as f:
            content = f.read()
            f.close()

        with open(rom, 'rb') as f:
            gbaBytes = list(f.read())
            f.close()        

        compile(content, gbaBytes)

        # Write it back to a .bin file
        with open(rom, 'wb') as f:
            f.write(bytes(gbaBytes))
            f.close()

        print("Done! Successfully compiled to %s" % rom)

    #x----------------------------------------------------------------------Misc extra commands-----------------------------------------------X
    elif selection[0] == "exit":
        break
    
    elif selection == "":
        continue
    
    else:
        print(selection + " is not a command")

print("Thank you for using tengokompiler! Now closing...")