#!/bin/sh
#
# humancoordload.sh
############################################################################
#
# Purpose:
#
# 	1. Parse the Alliance Human Coordinate JSON file - 
#           * Do QC
#           * Create a load ready coordload file
#       2. Invoke coordinate loader using the load ready file
#	3. update MRK_Location_Cache table
#
#  Env Vars:
#
#      See the configuration file
#
#  Inputs:
#
#      - Common configuration file -
#               /usr/local/mgi/live/mgiconfig/master.config.sh
#      - load configuration file - humancoordload.config
#      - coordinate load config file - coordload.config
#      - input file - See http://mgiwiki/mediawiki/index.php/sw:Humancoordload
#
#  Outputs:
#
#       - An archive file
#       - Log files defined by the environment variables ${LOG_PROC},
#        ${LOG_DIAG}, ${LOG_CUR} and ${LOG_VAL}
#       - QC reports written to ${RPTDIR}
#       - bcp files
#       - Records written to the database tables
#       - Exceptions written to standard error
#       - Configuration and initialization errors are written to a log file
#        for the shell script
#
#  Exit Codes:
#
#      0:  Successful completion
#      1:  Fatal error occurred
#      2:  Non-fatal error occurred
#
#  Assumes:  Nothing

# History
#
# 05/05/2023	sc
#	- FL2-300
#
###########################################################################

#
#  Set up a log file for the shell script in case there is an error
#  during configuration and initialization.
#

cd `dirname $0`/..
LOG=`pwd`/`basename $0`.log
rm -rf ${LOG}
touch ${LOG}

USAGE="humancoordload.sh"
#
#  Verify the argument(s) to the shell script.
#
if [ $# -ne 1 ]
then
    echo ${USAGE} | tee -a ${LOG}
    exit 1
fi

LOAD_CACHE=$1

#
# verify & source the load configuration file
#

CONFIG_LOAD=`pwd`/humancoordload.config

if [ ! -r ${CONFIG_LOAD} ]
then
    echo "Cannot read configuration file: ${CONFIG_LOAD}"
    exit 1
fi

. ${CONFIG_LOAD}

#
# verify the coordinate load configuration file
#

CONFIG_COORD=`pwd`/coordload.config

if [ ! -r ${CONFIG_COORD} ]
then
    echo "Cannot read configuration file: ${CONFIG_COORD}"
    exit 1
fi

#
#  Source the DLA library functions.
#

if [ "${DLAJOBSTREAMFUNC}" != "" ]
then
    if [ -r ${DLAJOBSTREAMFUNC} ]
    then
        . ${DLAJOBSTREAMFUNC}
    else
        echo "Cannot source DLA functions script: ${DLAJOBSTREAMFUNC}" | tee -a ${LOG}
        exit 1
    fi
else
    echo "Environment variable DLAJOBSTREAMFUNC has not been defined." | tee -a ${LOG}
    exit 1
fi

#
# check that the INPUT_FILE_DEFAULT has been set and exists
#
if [ "${INPUT_FILE_DEFAULT}" = "" ]
then
     # set STAT for endJobStream.py called from postload in shutDown
    STAT=1
    checkStatus ${STAT} "INPUT_FILE_DEFAULT not defined"
fi

##################################################################
##################################################################
#
# main
#
##################################################################
##################################################################

#
# createArchive including OUTPUTDIR, startLog, getConfigEnv, get job key
#

preload ${OUTPUTDIR}

#
# There should be a "lastrun" file in the input directory that was created
# the last time the load was run for this input file. If this file exists
# and is more recent than the input file, the load does not need to be run.
#
LASTRUN_FILE=${INPUTDIR}/lastrun
if [ -f ${LASTRUN_FILE} ]
then
    if test ${LASTRUN_FILE} -nt ${INPUT_FILE_DEFAULT}
    then

        echo "Input file has not been updated - skipping load" | tee -a ${LOG_PROC}
        # set STAT for shutdown
        STAT=0
        echo 'shutting down'
        shutDown
        exit 0
    fi
fi

#
# rm files and dirs from OUTPUTDIR
#

cleanDir ${OUTPUTDIR}

# remove old unzipped file
rm -rf ${INPUT_FILE}

# unzip the /data/downloads file to the input directory
echo "gunzip -c ${INPUT_FILE} > ${INPUT_FILE_DEFAULT}" | tee -a ${LOG}
gunzip -c ${INPUT_FILE} > ${INPUT_FILE_DEFAULT}

# get the build number from the input file
# we need to pass this to the java system properties when calling the coordload

cd ${INPUTDIR}

build=`cat /data/downloads/fms.alliancegenome.org/download/BGI_HUMAN.json | grep '"assembly": ' | cut -d: -f2 | cut -d'"' -f2 | sort | uniq`

echo "build: ${build}"

#
# process the input file
#
echo "" >> ${LOG_DIAG} 
echo "`date`" >> ${LOG_DIAG} 
echo "Processing input file ${INPUT_FILE_DEFAULT}" | tee -a ${LOG_DIAG}
${HUMANCOORDLOAD}/bin/humancoordload.py | tee -a ${LOG_DIAG} ${LOG_PROC}
STAT=$?
checkStatus ${STAT} "${HUMANCOORDLOAD}/bin/humancoordload.py"

#
# run the coordinate load
#
. ${CONFIG_COORD}
echo "" >> ${LOG_DIAG}
echo "`date`" >> ${LOG_DIAG}
echo "Running human coordinate java load" | tee -a ${LOG_DIAG} ${LOG_PROC}
${JAVA} ${JAVARUNTIMEOPTS} -classpath ${CLASSPATH} \
    -DCONFIG=${CONFIG_MASTER},${CONFIG_COORD} \
    -DCOORD_VERSION="${build}" \
    -DJOBKEY=${JOBKEY} ${DLA_START}

STAT=$?
checkStatus ${STAT} "human coordinate java load"

#
# now source the human coordload config to 
# ?? do we need to do this?
. ${CONFIG_LOAD}

#
# Load the marker location cache?
#
if [ ${LOAD_LOCATION_CACHE} = "true" ]
then
    echo "" >> ${LOG_DIAG}
    echo "`date`" >> ${LOG_DIAG}
    echo "Running marker location cacheload"| tee -a ${LOG_DIAG}
    ${LOCATIONCACHE_SH} >> ${LOG_DIAG}
    STAT=$?
    checkStatus ${STAT} "${LOCATIONCACHE_SH}"
fi

#
# Touch the "lastrun" file to note when the load was run.
#
if [ ${STAT} = 0 ]
then
    touch ${LASTRUN_FILE}
fi

#
# Perform post-load tasks.
#
shutDown

exit 0
