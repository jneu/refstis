#!/usr/bin/env python

"""Script to fill database with cos anneal month start and end times.  
"""

from __future__ import division

import sqlite3
import glob
import os
import sys
import pyfits
import support
import time
import shutil
from datetime import datetime
import pylab
import pdb
import re
import numpy as np
from support import SybaseInterface
from support import createXmlFile, submitXmlFile
from REFSTI_functions import figure_days_in_period,figure_number_of_periods,translate_date_string

import REFSTI_pop_db

import REFSTI_basedark
import REFSTI_weekdark

import REFSTI_refbias
import REFSTI_weekbias

import REFSTI_basejoint

import REFSTI_functions


#### Needs 
#mjd converter
#get_directories
#anneal_dir

#products_directory = '/grp/hst/stis/referencefiles/darks_biases/'
#retrieve_directory = '/grp/hst/stis/referencefiles/darks_biases/requested/'
products_directory = '/user/ely/STIS/refstis_mark2/darks_biases/'
retrieve_directory = '/user/ely/STIS/refstis_mark2/requested/'

#dark_proposals = [7600, 7601, 8408, 8437, 8837, 8864, 8901, 8902, 9605, 9606, 
#                  10017, 10018, 11844, 11845, 12401, 12402, 12741, 12742]
#bias_proposals = [7600, 7601, 8409, 8439, 8838, 8865, 8903, 8904, 9607, 9608, 
#                  10019, 10020, 11846, 11847, 12403, 12404, 12743, 12744]

dark_proposals = [ 11844, 11845, 12400, 12401, 12741, 12742, 13131, 13132]
bias_proposals = [ 11846, 11847, 12402, 12403, 12743, 12744, 13133, 13134]

#-------------------------------------------------------------------------------

def list_retreieved_files( folder ):
    for root,dirs,files in os.walk( folder ):
        file_list = glob.glob('?????????_raw.fits')

#-------------------------------------------------------------------------------

def get_new_periods():
    print '#-------------------#'
    print 'Reading from database'
    print '#-------------------#\n\n'
    db = sqlite3.connect("/user/ely/STIS/refstis_mark2/my_scripts/anneal_info")
    c = db.cursor()
    table = 'anneals'

    c.execute("""SELECT * FROM %s """%(table))

    all_info = [row for row in c]

    table_id_all = [row[0] for row in all_info]
    proposal_id_all = [row[1] for row in all_info]
    visit_id_all = [ int(row[2]) for row in all_info ]
    anneal_start_all = [row[3] for row in all_info]
    anneal_end_all = [row[4] for row in all_info]

    dirs_to_process = []

    for i in range( len(table_id_all) )[::-1]:
        if i == len(table_id_all)-1: continue
        ref_begin = anneal_end_all[i]
        ref_end = anneal_start_all[i+1]
        proposal = proposal_id_all[i]  ### make this i+1 # defined as the next poposal
        visit = visit_id_all[i+1]
        year,month,day,dec_year = support.mjd_to_greg(ref_begin)
        end_year,end_month,end_day,dec_year = support.mjd_to_greg(ref_end)       
 
        if visit < 10:
            visit = '0'+str(visit)
        else:
            visit = str(visit)

        print '\n\n#--------------------#'
        print '%d_%d_%s  MJD %5.5f : %5.5f'%(year,proposal,visit,ref_begin,ref_end)
        print month,day,year,' : ',end_month,end_day,end_year
        print '#--------------------#'

        products_folder = os.path.join( products_directory,'%d_%d_%s'%(year,proposal,visit) )
        dirs_to_process.append( products_folder )

        if not os.path.exists( products_folder ): 
            os.mkdir( products_folder )
        
        already_retrieved = []
        for root,dirs,files in os.walk( products_folder ):
            for item in glob.glob( os.path.join(root,'?????????_raw.fits') ):
                already_retrieved.append( os.path.split(item)[-1][:9].upper() )
        #already_retrieved = [ os.path.split(item)[1][:9] for item in glob.glob( os.path.join(products_folder,'?????????_raw.fits') ) ]

        new_obs = get_new_obs('DARK',ref_begin,ref_end) + get_new_obs('BIAS',ref_begin,ref_end)  ###Grab both darks and biases before moving on to collect and move.
        obs_to_get = [ obs for obs in new_obs if not obs in already_retrieved ]

        if not len( obs_to_get ): 
            print 'No new obs to get, skipping this period'
            continue
        else: 
            print 'Found new observations for this period'
            print obs_to_get

        #raw_input('#------  continue on?  --------#')
        ## response = collect_new( obs_to_get )
        ## move_obs( obs_to_get, products_folder) 

        ## separate_obs( products_folder, ref_begin, ref_end )

    return dirs_to_process

#-------------------------------------------------------------------------------

def make_ref_files( root_folder ):
    print 'Working on ',root_folder

    bias_threshold = { (1,1,1):98, (1,1,2):25, (1,2,1):25, (1,2,2):7,
                       (1,4,1):7, (1,4,2):4, (4,1,1):1 }

    gain_folders = []
    week_folders = []
    for root,dirs,files in os.walk( root_folder ):
        tail = os.path.split( root )[-1]
        if 'wk' in tail:     
            week_folders.append( root )
        if re.search('([0-4]-[0-4]x[0-4])',tail):
            gain_folders.append( root )
        

    ####################
    # make the base biases
    ####################

    for folder in gain_folders:
        all_dir = os.path.join( folder,'all' )
        if not os.path.exists( all_dir ):  os.mkdir( all_dir )

        for root,dirs,files in os.walk( folder ):
            if root.endswith('all'): continue
            for filename in files:
                if filename.endswith('_raw.fits'):
                    shutil.copy( os.path.join( root, filename), all_dir )

        all_files = glob.glob( os.path.join( all_dir, '*_raw.fits') )
        bb_name = os.path.join( all_dir,'bb.fits' )
        print 'Running basejoint '
        print all_dir
        REFSTI_basejoint.make_basebias( all_files ,bb_name )


    ####################
    # make the week biases
    ####################

    for folder in week_folders:
        REFBIAS = False
        BASEJOIN = False
        WEEKBIAS = False
 
        BASEDARK = False
        WEEKDARK = False
        print 'Processing %s'%(folder)

        proposal = re.search('(_[0-9]{5}_)',folder).group().strip('_')
        wk = re.search('([bi]*wk0[0-9])',folder).group()

        raw_files = glob.glob( os.path.join( folder, '*raw.fits') )
        n_imsets = REFSTI_functions.count_imsets( raw_files )

        if n_imsets > 200: 
            sys.exit('error, too many imsets fonud: %d'%(n_imsets) )
        
        gain = REFSTI_functions.get_keyword( raw_files, 'CCDGAIN', 0)
        xbin = REFSTI_functions.get_keyword( raw_files, 'BINAXIS1', 0)
        ybin = REFSTI_functions.get_keyword( raw_files, 'BINAXIS2', 0)
        
        if re.search('/biases/',folder):
            filetype = 'bias'
            REFBIAS = True

            if n_imsets < bias_threshold[ (gain,xbin,ybin) ]:
                BASEJOIN = True
                WEEKBIAS = True

        elif re.search('/darks/',folder):
            filetype = 'dark'
            BASEDARK = True
            WEEKDARK = True

        else:
            print 'ERROR',folder
            sys.exit()

        ref_base_name = os.path.join( folder, '%s_%s_%s'%(filetype,proposal,wk) )
        print folder, filetype
        print '%d files found with %d imsets'%(len(raw_files),n_imsets)

        if REFBIAS: 
            refbias_name = os.path.join( folder, 'refbias_%s_%s'%(proposal,wk) )
            REFSTI_refbias.make_refbias( raw_files, refbias_name )

        if WEEKBIAS:
            sys.ext('I needed to run weekbias')
            pass
        if BASEJOIN: pass

        if BASEDARK: pass
        if WEEKDARK: pass
                                                                  

#-------------------------------------------------------------------------------

def get_new_obs(file_type, start, end):

    if file_type == 'DARK':
        proposal_list = dark_proposals
        MIN_EXPTIME = 1000
        MAX_EXPTIME = 1200
    elif file_type == 'BIAS':
        proposal_list = bias_proposals
        MIN_EXPTIME = -1
        MAX_EXPTIME = 100
    else:
        print 'file type not recognized: ',file_type

    query = support.SybaseInterface("ZEPPO","dadsops")

    OR_part = "".join(["science.sci_pep_id = %d OR "%(proposal) for proposal in proposal_list])[:-3]

    #obs_name_query = "SELECT science.sci_data_set_name FROM science WHERE ( " + OR_part + " ) AND  science.sci_targname ='%s' AND science.sci_actual_duration BETWEEN %d AND %d "%(file_type,MIN_EXPTIME,MAX_EXPTIME)
    #start_time_query = "SELECT science.sci_start_time FROM science WHERE ( " + OR_part + " ) AND  science.sci_targname ='%s' AND science.sci_actual_duration BETWEEN %d AND %d "%(file_type,MIN_EXPTIME,MAX_EXPTIME)

    data_query = "SELECT science.sci_start_time,science.sci_data_set_name FROM science WHERE ( " + OR_part + " ) AND  science.sci_targname ='%s' AND science.sci_actual_duration BETWEEN %d AND %d "%(file_type,MIN_EXPTIME,MAX_EXPTIME)
    query.doQuery(query=data_query)
    new_dict = query.resultAsDict()
 
    #query.doQuery(query=obs_name_query)
    #new_dict = query.resultAsDict()
    #obs_names = new_dict[new_dict.keys()[0]][2:]  #remove non-obs entries in dictionary

    #query.doQuery(query=start_time_query)
    #new_dict = query.resultAsDict()
    #start_times = new_dict[new_dict.keys()[0]][2:]  #remove non-obs entries in dictionary
    
    obs_names = np.array( new_dict['sci_data_set_name'] )
    
    start_times_MJD = np.array( map(translate_date_string,new_dict['sci_start_time'] ) )
    #start_times_MJD = np.array( [ translate_date_string(item) for item in start_times ] )
    
    index = np.where( (start_times_MJD > start) & (start_times_MJD < end) )[0]

    assert start_times_MJD[index].min() > start, 'Data has mjd before period start'
    assert start_times_MJD[index].max() < end, 'Data has mjd after period end'

    datasets_to_retrieve = obs_names[index]
    dataset_times = start_times_MJD[index]

    return list(datasets_to_retrieve)

#-----------------------------------------------------------------------

def collect_new(observations_to_get):
    '''
    Function to find and retrieve new datasets for given proposal.
    Uses modules created by B. York: DADSAll.py and SybaseInterface.py.
    '''
    print '#----------------------------#'
    print 'Searching for new observations'
    print '#----------------------------#'

    xml = createXmlFile(ftp_dir= retrieve_directory, 
                      set=observations_to_get, file_type='RAW', 
                      archive_user='ely', 
                      archive_pwd='etacar', email='ely@stsci.edu', 
                      host='science3.stsci.edu', 
                      ftp_user='ely', ftp_pwd='5correctmonkeys')

    response = submitXmlFile(xml,'dmsops1.stsci.edu')
    if ('SUCCESS' in response):
        success=True
    else:
        success=False
    success = True

    return success

#-----------------------------------------------------------------------

def separate_obs( base_dir, month_begin, month_end  ):
    all_files = glob.glob( os.path.join(base_dir,'*raw.fits') )
    N_days_total = int(month_end - month_begin)
    N_days_remainder = (month_end - month_begin) - N_days_total

    print 'Separating',base_dir
    print
    print 'Period runs from',month_begin,' to ', month_end

    mjd_times = np.array( [ pyfits.getval(item,'EXPSTART',ext=1) for item in all_files ] )
    print 'Data goes from',mjd_times.min(), ' to ', mjd_times.max()

    print 'Making Lists'
    bias_111_list = [item for item in all_files if ( pyfits.getval(item,'TARGNAME',ext=0)=='BIAS') & ( pyfits.getval(item,'CCDGAIN',ext=0) == 1) ]
    bias_411_list = [item for item in all_files if ( pyfits.getval(item,'TARGNAME',ext=0)=='BIAS') & ( pyfits.getval(item,'CCDGAIN',ext=0) == 4) ]
    dark_111_list = [item for item in all_files if ( pyfits.getval(item,'TARGNAME',ext=0)=='DARK') & ( pyfits.getval(item,'CCDGAIN',ext=0) == 1) ]
    print 'Done'

    for obs_list,file_type,mode in zip( [bias_111_list,dark_111_list,bias_411_list],
                                        ['BIAS','DARK','BIAS'],
                                        ['WK','WK','BIWK'] ):
        gain = list( set( [ pyfits.getval(item,'CCDGAIN',ext=0) for item in obs_list ] ) )
        assert len(gain) == 1, 'ERROR: Not everything has the same gain'
        gain = gain[0]

        N_periods = figure_number_of_periods(N_days_total, mode)

        N_days_per_period = figure_days_in_period(N_periods, N_days_total)
        N_days_per_period[-1] += N_days_remainder

        print
        print file_type, mode, 'will be broken up into %d periods as follows:'%(N_periods)
        print N_days_per_period
        print

        for period in range(N_periods):
            if period == 0:  
                begin = month_begin
            else: 
                begin = end
            
            end = begin + N_days_per_period[period]

            week = str(period + 1) ##weeks from 1-4, not 0-3
            while len(week) < 2:
                week = '0'+week            

            output_path = base_dir
            if file_type == 'BIAS':
                output_path = os.path.join(output_path, 'biases/%d-1x1/%s%s/'%(gain,mode.lower(),week) )
            elif file_type == 'DARK':
                output_path = os.path.join(output_path, 'darks/%s%s/'%(mode.lower(),week) )
            else: print 'File Type not recognized'
            
            print output_path
            if not os.path.exists( output_path ): 
                os.makedirs( output_path )

            print 'week goes from: ',begin,end
            obs_to_move = [ item for item in obs_list if 
                            ( (pyfits.getval(item,'EXPSTART',ext=1) >= begin) and 
                              (pyfits.getval(item,'EXPSTART',ext=1) < end) ) ]
            print begin,end, obs_to_move
            if not len(obs_to_move):
                print 'error, empty list to move'

            for item in obs_to_move:
                print 'Moving ',item, ' to:',output_path
                shutil.move( item, output_path )
                obs_list.remove( item )

#-----------------------------------------------------------------------

def move_obs(new_obs, base_output_dir):
    print 'Files not yet delivered.'
    delivered_set = set( [ os.path.split(item)[-1][:9].upper() for item in glob.glob( os.path.join(retrieve_directory,'*raw*.fits') ) ] )
    new_set = set( new_obs )

    while not new_set.issubset( delivered_set ):
        wait_minutes=2
        time.sleep(wait_minutes*60) #sleep for 2 min
        delivered_set = set( [ os.path.split(item)[-1][:9].upper() for item in glob.glob( os.path.join(retrieve_directory,'*raw*.fits') ) ] )

    assert len(new_obs)>0, 'Empty list of new observations to move'

    if not os.path.exists( base_output_dir):
        os.makedirs( base_output_dir )

    list_to_move = [ os.path.join( retrieve_directory, item.lower()+'_raw.fits') for item in new_obs ]

    for item in list_to_move:
        print 'Moving ',item, ' to:',base_output_dir
        shutil.move( item, base_output_dir )

    list_to_remove = glob.glob( os.path.join(retrieve_directory,'*.fits') )
    for item in list_to_remove:
        os.remove(item)

#-------------------------------------------------------------------------------

def main():
    REFSTI_pop_db.main()

    all_folders = get_new_periods()

    for folder in all_folders:
        make_ref_files( folder )

if __name__ == "__main__":
    main()
