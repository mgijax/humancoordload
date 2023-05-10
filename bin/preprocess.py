#
#  humancoordload.py
###########################################################################
#
#  Purpose:
#
#      This script will parse the Alliance Human Coordinate file 
#      run QC and generate a file for the coordinate load product (coordload).
#
#  Env Vars:
#       Also see the configuration file (humancoordload.config)
#      The following environment variables are set by the configuration
#      file that is sourced by the wrapper script (humancoordload.config):
#
#          INPUT_FILE - /data/downloads gzipped file
#          INPUT_FILE_DEFAULT - unzipped form of gzipped file in ${INPUTDIR}
#          INPUT_FILE_LOAD - coordload format file with any skipped QC removed
#          QC_NomenMisMatch
#          QC_ChrMisMatch
#          QC_MultipleCoords
#
#  Inputs:
#
#      Alliance human coordinate file in json format 
#           downloaded gzipped: ${INPUT_FILE}
#           unzipped ${INPUT_FILE_DEFAULT}
#
#  Outputs:
#
#  * coordload format file: http://bhmgiwk01lp.jax.org/mediawiki/index.php/sw:Coordload#Input_File_Format
#       
#       1. NCBI ID 
#       2. Chromosome
#       3. Start Coordinate
#       4. End Coordinate
#       5. Strand (+ or - or null)
#   * Nomenclature mismatch report
#   * Chromosome mismatch report
#   * Multiple coordinate report
#
USAGE="usage: preprocess.py"
#
#      humancoordload.py
#
#  Exit Codes:
#
#      0:  Successful completion
#      1:  An exception occurred
#
#  Assumes:  Nothing
#
#  Implementation:
#
#      This script will perform following steps:
#
#      1) Initialize variables.
#      2) Open files.
#      3) Writes QC
#      4) Writes load ready file       
#      5) Close files.
#
#  Notes:  None
#
###########################################################################

import sys 
import os
import json
import string
import db

TAB = '\t'
CRT = '\n'


# Alliance file
inputFile = None

# INPUT_FILE_LOAD
coordFile = None

# QC_NomenMisMatch
nomenMisMatchFile = None

# QC_ChrMisMatch
chrMisMatchFile = None

# QC_MultipleCoords
multipleCoordsFile = None

curatorLog = None

# file pointers
fpInput = None
fpLoad = None
fpCurLog = None

fpNomenMisMatch = None
fpChrMisMatch = None
fpMultipleCoords = None

# lookup of MGI Human data (NCBI id, symbol, chromosome)
mgiLookup = {}

# lookup of human symbols
# genes with no location
noLocationList = []

# genes with no NCBI ID
noNcbiIdList = []

# genes with multiple coordinates
multipleCoordsList = []

# To count genes with multi coordinates
multipleCoordsCt = 0

# gene whose NCBI IDs are not in the database
ncbiNotInMGIList = []

# list of chr mismatches that will be written to a report
chrMisMatchList = []

# list of nomen mismatches that will be written to a report
nomenMisMatchList = []

# {ncbiID: [list of coordload lines]
# we will skip loading of any ncbiIDs with multi coords
toLoadDict = {}

#
# Purpose: Initialization
# Returns: 1 if file does not exist or is not readable, else 0
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def initialize():
    global inputFile, coordFile, nomenMisMatchFile, chrMisMatchFile, multipleCoordsFile
    global fpInput, fpLoad, fpNomenMisMatch, fpChrMisMatch, fpMultipleCoords
    global curatorLog, fpCurLog

    inputFile = os.getenv('INPUT_FILE_DEFAULT')
    coordFile = os.getenv('INPUT_FILE_LOAD')
    curatorLog = os.getenv('LOG_CUR')
    nomenMisMatchFile = os.getenv('QC_NomenMisMatch')
    chrMisMatchFile = os.getenv('QC_ChrMisMatch')
    multipleCoordsFile = os.getenv('QC_MultipleCoords')

    rc = 0

    #
    # Make sure the environment variables are set.
    #
    if not inputFile:
        print('Environment variable not set: INPUT_FILE')
        rc = 1

    if not coordFile:
        print('Environment variable not set: INPUT_FILE_LOAD')
        rc = 1

    if not curatorLog:
        print('Environment variable not set: LOG_CUR')
        rc = 1

    if not nomenMisMatchFile:
        print('Environment variable not set: QC_NomenMisMatch')
        rc = 1

    if not chrMisMatchFile:
        print('Environment variable not set: QC_ChrMisMatch')
        rc = 1

    if not multipleCoordsFile:
        print('Environment variable not set: QC_MultipleCoords')
        rc = 1

    #
    # Initialize file pointers.
    #
    fpInput = None
    fpLoad = None
    fpCurLog = None
    fpNomenMisMatch = None
    fpChrMisMatch = None
    fpMultipleCoords = None

    return rc


#
# Purpose: Open files.
# Returns: 1 if file does not exist or is not readable, else 0
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def openFiles():
    global fpInput, fpLoad, fpCurLog, fpNomenMisMatch, fpChrMisMatch, fpMultipleCoords
    global mgiLookup

    #
    # Open the input file. this is a json file.
    #
    try:
        fpInput = open(inputFile, 'r')
    except:
        print('Cannot open file: %s' % inputFile)
        return 1

    #
    # Open the coordinate file.
    #
    try:
        fpLoad = open(coordFile, 'w')
    except:
        print('Cannot open file: %s' % coordFile)
        return 1

    #
    # Open the curator log
    #
    try:
        fpCurLog = open(curatorLog, 'w')
    except:
        print('Cannot open file: %s' % curatorLog)
        return 1

    #
    # Open the nomenclature mismatch file.
    #
    try:
        fpNomenMisMatch = open(nomenMisMatchFile, 'w')
    except:
        print('Cannot open file: %s' % nomenMisMatchFile)
        return 1

    #
    # Open the chromosome mismatch file.
    #
    try:
        fpChrMisMatch = open(chrMisMatchFile, 'w')
    except:
        print('Cannot open file: %s' % chrMisMatchFile)
        return 1

    #
    # Open the multiple coordinates file.
    #
    try:
        fpMultipleCoords = open(multipleCoordsFile, 'w')
    except:
        print('Cannot open file: %s' % multipleCoordsFile)
        return 1

    #
    # write headers for qc reports
    #

    fpNomenMisMatch.write('''
Human Gene Coordinates Load - Nomenclature Mismatches

Report of human genes with coordinates whose nomenclature in the coordinate input file 
  is not the same as loaded by the Entrez Gene load in the MGI Database. These are loaded.

''')


    fpNomenMisMatch.write("column 1 : Gene ID from NCBI\n")
    fpNomenMisMatch.write("column 2 : Symbol in Coordinates file\n")
    fpNomenMisMatch.write("column 3 : Symbol in MGI's current data\n\n")

    fpChrMisMatch.write('''
Human Gene Coordinates Load - Chromosome Mismatches

Report of human genes with coordinates whose chromosome in the coordinates input file 
  is not the same as loaded by the Entrez Gene load in the MGI Database. These are not loaded.   
 
''')

    fpChrMisMatch.write("column 1 : Gene ID from NCBI\n")
    fpChrMisMatch.write("column 2 : Chromosome in Coordinates file\n")
    fpChrMisMatch.write("column 3 : Chromosome in MGI's current data\n\n")

    fpMultipleCoords.write('''
Human Gene Coordinates Load - Multiple Coordinates

Report of human genes that have multiple sets of coordinates in the input file.
  These are not loaded.

''')

    fpMultipleCoords.write("Each Stanza represents a Gene's Coordinates and consists of:\n")
    fpMultipleCoords.write("Line 1 : Gene Symbol and NCBI ID\n")
    fpMultipleCoords.write("Lines 2-n : one set of key/value pairs for each coordinate for the gene\n\n")

    #
    # Select all human markers that contain EntrezGene ids
    # and are statused as 'official'
    #
    results = db.sql('''
        select a.accID, m.symbol, m.chromosome
        from MRK_Marker m, ACC_Accession a
        where m._Organism_key = 2
        and m._Marker_Status_key = 1
        and m._Marker_key = a._Object_key
        and a._MGIType_key = 2
        and a._LogicalDB_key = 55
        ''', 'auto')

    # store this set in the mgiLookup
    for r in results:
        egID = r['accID']
        mgiLookup[egID] = r

    return 0


#
# Purpose: Close files.
# Returns: 1 if file does not exist or is not readable, else 0
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def closeFiles():

    if fpInput:
        fpInput.close()

    if fpLoad:
        fpLoad.close()

    if fpCurLog:
        fpCurLog.close()

    if fpNomenMisMatch:
        fpNomenMisMatch.close()

    if fpChrMisMatch:
        fpChrMisMatch.close()

    if fpMultipleCoords:
        fpMultipleCoords.close()

    return 0


#
# Purpose: Use Alliance json file to generate coordinate file.
# Returns: 1 if file does not exist or is not readable, else 0
# Assumes: Nothing
# Effects: Nothing
# Throws: Nothing
#
def preprocess():
    global multipleCoordsCt

    jFile = json.load(fpInput)

    #
    # Process each record 
    #
    for f in jFile['data']:
        #print('f: %s' % f)
        allianceSymbol = f['symbol']
        #print('symbol: %s' % allianceSymbol)
        
        basic = f['basicGeneticEntity']
        try:
            locations = basic['genomeLocations']
        except:
            noLocationList.append('%s%s' % (allianceSymbol, CRT))
            continue
        #print('locations: %s' % locations)
        #if len(locations) > 1:
        #    fpMultipleCoords.write(%s%s%s%s' % (allianceSymbo, TAB, locations)) 
        #location = locations[0]
        #chromosome = location['chromosome']
        #start = location['startPosition']
        #end =  location['endPosition']
        #strand = location['strand']

        xrefs = basic['crossReferences']
        #print('xrefs: %s' % xrefs)

        geneID = ''
        for x in xrefs:
            if x.get('id') != None:
                keyValue= x['id'].split(':')
                if keyValue[0] == 'NCBI_Gene':
                    geneID = keyValue[1]
                    #print('keyValue: %s' % keyValue)
        if geneID == '':
            noNcbiIdList.append('%s%s' % (allianceSymbol, CRT))
            continue   
        #print('geneID: %s chromosome: %s start: %s end: %s strand: %s' % (geneID, chromosome, start, end, strand))

        #print('locations: %s' % locations)
        if len(locations) > 1:
            multipleCoordsList.append('%s%s%s:%s' % (allianceSymbol, TAB, geneID, CRT))
            multipleCoordsCt += 1
            for l in locations:
                multipleCoordsList.append('    %s%s' % (l, CRT))
            continue
        else:
            location = locations[0]
            chromosome = location['chromosome']
            start = location['startPosition']
            end =  location['endPosition']
            strand = location['strand']

        # skip if the NCBI ID does not exist in MGI 
        if geneID not in mgiLookup:
            #print('NCBI Gene ID not in MGI for : %s %s' % (allianceSymbol, geneID)) 
            ncbiNotInMGIList.append('%s%s%s%s' % (allianceSymbol, TAB, geneID, CRT))
            continue

        # skip if chromosome values do not match
        mgiChromosome = mgiLookup[geneID]['chromosome']
        if mgiChromosome != chromosome:
            chrMisMatchList.append('%s%s%s%s%s%s' % (geneID, TAB, chromosome, TAB, mgiChromosome, CRT))
            continue

        # check if NCBI symbol do not match the MGD symbol
        # allow the load, but report the difference
        mgiSymbol = mgiLookup[geneID]['symbol']
        if mgiSymbol != allianceSymbol:
            nomenMisMatchList.append('%s%s%s%s%s%s' % (geneID, TAB, allianceSymbol, TAB, mgiSymbol, CRT))

        if geneID not in toLoadDict:
            toLoadDict[geneID] = []
        toLoadDict[geneID].append('%s%s%s%s%s%s%s%s%s%s' % (geneID, TAB, chromosome, TAB, start, TAB, end, TAB, strand, CRT)) 
    for geneID in toLoadDict:
            fpLoad.write(CRT.join(toLoadDict[geneID]))

    if len(chrMisMatchList):
        fpChrMisMatch.write(''.join(chrMisMatchList))
        fpChrMisMatch.write('Total: %s' % len(chrMisMatchList))

    if len(nomenMisMatchList):
        fpNomenMisMatch.write(''.join(nomenMisMatchList))
        fpNomenMisMatch.write('Total: %s' % len(nomenMisMatchList))

    if len(multipleCoordsList):
        fpMultipleCoords.write(''.join(multipleCoordsList))
        fpMultipleCoords.write('Total: %s' % multipleCoordsCt)
    fpLoad.close()

    return 0

def writeQC():
    if len(noLocationList):
        fpCurLog.write('Human Symbols with No Coordinates in the Input File:%s' % CRT)
        for symbol in noLocationList:
            fpCurLog.write('%s' % symbol)
        fpCurLog.write('Total: %s%s' % (len(noLocationList), CRT))

    if len(noNcbiIdList):
        fpCurLog.write('%sHuman Symbols with No NCBI ID in the Input File:%s' % (CRT, CRT))
        for symbol in noNcbiIdList:
            fpCurLog.write('%s' % symbol)
        fpCurLog.write('Total: %s%s' % (len(noNcbiIdList), CRT))

    if len(ncbiNotInMGIList):
        fpCurLog.write('%sHuman Symbols where NCBI ID is not in the Database:%s' % (CRT, CRT))
        for line in ncbiNotInMGIList:
            fpCurLog.write('%s' % line)
        fpCurLog.write('Total: %s%s' % (len(ncbiNotInMGIList), CRT))
#
#  MAIN
#

if initialize() != 0:
    sys.exit(1)

if openFiles() != 0:
    sys.exit(1)

if preprocess() != 0:
    closeFiles()
    sys.exit(1)

if writeQC() != 0:
    closeFiles()
    sys.exit(1)

closeFiles()
sys.exit(0)
