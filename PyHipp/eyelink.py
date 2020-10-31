from pyedfread import edfread
import numpy as np
import numpy.matlib
import pandas as pd
import hickle as hkl
import os
import math
import matplotlib.pyplot as plt
import matplotlib.lines as lines
import matplotlib.patches as patches
import DataProcessingTools as DPT
from .rplparallel import RPLParallel

class EDFSplit(DPT.DPObject):

    filename = 'edfsplit.hkl'
    argsList = [('FileName', '.edf'), ('CalibFileNameChar', 'P'), ('NavDirName', 'session0'), 
    ('CalibDirName', 'sessioneye'), ('TriggerMessage', 'Trigger Version 84')]
    level = 'day'

    def __init__(self, *args, **kwargs):
        # create object in day directory
        DPT.DPObject.__init__(self, *args, **kwargs)

    def create(self, *args, **kwargs):
        self.samples = pd.DataFrame()
        self.messages = pd.DataFrame()
        self.events = pd.DataFrame()
        # header variables
        self.esr = 0
        self.expTime = 0
        self.timeouts = pd.DataFrame()
        self.actualSessionNo = 0
        self.noOfTrials = 0
        self.noOfSessions = 0
        
        # already present in day directory
        files = os.listdir()
        calib_files = [i for i in files if i.endswith(self.args['FileName']) and self.args['CalibFileNameChar'] in i]
        nav_files = [i for i in files if i.endswith(self.args['FileName']) and self.args['CalibFileNameChar'] not in i]

        if not calib_files or not nav_files:
            print('Missing .edf files.')
            # create empty object
            DPT.DPObject.create(self, dirs=[], *args, **kwargs)
            return
 
        # number of sessions
        sessionName = []
        dirs = os.listdir()
        for file_name in dirs:
            if file_name.startswith(self.args['NavDirName']):
                sessionName.append(file_name)
        actualSessionNo = len(sessionName)
        self.actualSessionNo = actualSessionNo

        # if edf_split is called from Eyelink
        # if self.args['fromEyelink']:
        if kwargs.get('fromEyelink'):
            # if not self.args['sessionType']:
            if not kwargs.get('sessionType'):
                file_type = calib_files
            else:
                file_type = nav_files
            process_session(self, file_type, int(kwargs.get('sessionType')))
        else:
            edf_raw = process_session(self, calib_files, 0) # sessioneye
            Eyelink(raw_data=edf_raw, fromEDFSplit=True, sessionType=0, redoLevel=1, saveLevel=1)

            # calls Eyelink from edfsplit
            for idx in range(actualSessionNo):
                # this is where process_session needs to select the correct section of data from the edf file 
                edf_raw = process_session(self, nav_files, idx+1)
                Eyelink(raw_data=edf_raw, fromEDFSplit=True, sessionType=idx+1, redoLevel=1, saveLevel=1)
        
        DPT.DPObject.create(self, *args, **kwargs)
        return self

    def plot(self, i = None, ax = None, overlay = False):
            pass

def process_session(self, file, sessionType):
    # If edfsplit is called by a fixation session
    if not sessionType: # change to session_type
        # type == 0, 0 = sessioneye, 1 = session01...
        # creation of a sessioneye (fixation) object
        # calibration file w/ format: 'Pm_d.edf'
        print('Reading calibration edf file.\n')

        samples, events, messages = pread(
                file[0], trial_marker=b'1  0  0  0  0  0  0  0')

        # Header Variables
        # sampling rate
        esr = int(messages['RECCFG'][0][1])
        # expTime
        expTime = samples['time'].iloc[0]
        # noOfTrials
        noOfTrials = len(messages) - 1
        # noOfSessions
        noOfSessions = 1

    else: # for a navigation session
        # creation of a session# (navigation) object
        # navigation file w/ format: 'yymmdd.edf'
        print('Reading navigation edf file.\n')

        samples, events, messages = pread(
                file[0], trial_marker=b'Start Trial')

        samples2, events2, messages2 = pread(
                file[0], trial_marker=b'Trigger Version 84')
        print('Loaded edf')
        
        # Header Variables
        # sampling rate
        esr = int(messages['RECCFG'][0][1])
        # expTime
        expTime = samples['time'].iloc[0]
        # timeout
        timeouts = messages['Timeout_time'].dropna()
        # noOfTrials
        noOfTrials = len(messages) - 1
        # noOfSessions
        noOfSessions = len(messages2.index) - 1

        # create ranges of session
        trigger_m = messages2['trialid_time'].dropna().tolist()
        trigger_m[0] = 0.0
        trigger_m.append(999999999.0)

        # extract the correct session information
        # current using a for loop, the data is extracted in order the same number of times as the number of nav session folders that are present
        # this function needs to recognize the 'dummy' sessions from samples, events and messages returned by pyedfread
        i = sessionType - 1 # session01 gives i=0

        events = events[(events['end'] >= trigger_m[i]) & (events['start'] < trigger_m[i+1])]
        samples = samples[(samples['time'] >= trigger_m[i]) & (samples['time'] < trigger_m[i+1])]

    self.samples = samples
    self.messages = messages
    self.events = events
    self.esr = esr
    self.expTime = expTime
    self.timeouts = pd.DataFrame()
    self.noOfTrials = noOfTrials
    self.noOfSessions = noOfSessions

    return self

def pread(filename,
          ignore_samples=False,
          filter='all',
          split_char=' ',
          trial_marker=b'TRIALID',
          meta={}):
    '''
    Parse an EDF file into a pandas.DataFrame.
    EDF files contain three types of data: samples, events and messages.
    pread returns one pandas DataFrame for each type of information.
    '''
    if not os.path.isfile(filename):
        raise RuntimeError('File "%s" does not exist' % filename)

    if pd is None:
        raise RuntimeError('Can not import pandas.')

    samples, events, messages = edfread.fread(
        filename, ignore_samples,
        filter, split_char, trial_marker)
    events = pd.DataFrame(events)
    messages = pd.DataFrame(messages)
    samples = pd.DataFrame(np.asarray(samples), columns=edfread.sample_columns)

    for key, value in meta.items():
        events.insert(0, key, value)
        messages.insert(0, key, value)
        samples.insert(0, key, value)

    return samples, events, messages


class Eyelink(DPT.DPObject):
    '''
    Eyelink(redoLevel=0, saveLevel=0)
    '''
    filename = 'eyelink.hkl'
    argsList = [('FileName', '.edf'), ('CalibFileNameChar', 'P'), ('NavDirName', 'session0'), 
    ('DirName', 'session*'), ('CalibDirName', 'sessioneye'), ('ScreenX', 1920), ('ScreenY', 1080), 
    ('NumTrialMessages', 3), ('TriggerMessage', 'Trigger Version 84')]
    level = 'session'

    def __init__(self, *args, **kwargs):
        # create object in session directory        
        DPT.DPObject.__init__(self, *args, **kwargs)

    def create(self, *args, **kwargs):
        self.trial_timestamps = pd.DataFrame()
        self.calib_eye_pos = pd.DataFrame()
        self.eye_pos = pd.DataFrame()
        self.numSets =  []
        self.expTime = []
        self.indices = pd.DataFrame()
        self.timestamps = pd.DataFrame()
        self.timeouts = pd.DataFrame()
        self.noOfTrials = []
        self.fix_event = pd.DataFrame()
        self.sacc_event = pd.DataFrame()
        self.calib_fix_event = pd.DataFrame()
        self.calib_sacc_event = pd.DataFrame()
        self.fix_times = pd.DataFrame()
        self.trial_codes = pd.DataFrame()
        self.session_start = []
        self.session_start_index = []
        self.noOfSessions = []
        self.samplingRate = []
        self.discrepancies = []

        # check if arguments contain data
        if 'trial_timestamps' in kwargs.keys():
                if kwargs['trial_timestamps']:
                    self.trial_timestamps = kwargs['trial_timestamps']
                    self.eye_pos = kwargs['eye_pos']
                    self.numSets =  kwargs['numSets']
                    self.expTime = kwargs['expTime']
                    self.timestamps = kwargs['timestamps']
                    self.timeouts = kwargs['timeouts']
                    self.noOfTrials = kwargs['noOfTrials']
                    self.fix_event = kwargs['fix_event']
                    self.fix_times = kwargs['fix_times']
                    self.sacc_event = kwargs['sacc_event']
                    self.trial_codes = kwargs['trial_codes']
                    self.session_start = kwargs['session_start']
                    self.session_start_index = kwargs['session_start_index']
                    self.noOfSessions = kwargs['noOfSessions']
                    self.samplingRate = kwargs['samplingRate']
                    self.discrepancies = kwargs['discrepancies']
                
                    return self

        if not kwargs.get('fromEDFSplit'):
            # determine which session eyelink is being called in 
            cwd = os.getcwd()
            if not cwd.endswith(self.args['CalibDirName']):
                dir = cwd[-1]
            else:
                dir = 0
            os.chdir('..')
            
        files = os.listdir()
        calib_files = [i for i in files if i.endswith(self.args['FileName']) and self.args['CalibFileNameChar'] in i]
        nav_files = [i for i in files if i.endswith(self.args['FileName']) and self.args['CalibFileNameChar'] not in i]

        # no edf files
        if not calib_files or not nav_files:
            print('Missing edf files. Return empty object...')
            # create empty object
            DPT.DPObject.create(self, dirs=[], *args, **kwargs)
            return self
        else:
            # if called eyelink first
            if not kwargs.get('fromEDFSplit'):
                if not cwd.endswith(self.args['CalibDirName']):
                    os.chdir('session0' + str(dir))
                else:
                    os.chdir('sessioneye')

                # call edfsplit to extract information for that session
                edf_split = EDFSplit(sessionType=dir, fromEyelink=True)

                samples = edf_split.samples
                events = edf_split.events
                messages = edf_split.messages

            # if called edf_split first
            else:
                # get the session type
                # dir = self.args['sessionType']
                dir = kwargs.get('sessionType')
                if not dir:
                    os.chdir('sessioneye')
                else:
                    os.chdir('session0' + str(dir))

                edf_split = kwargs['raw_data']

                samples = edf_split.samples
                events = edf_split.events
                messages = edf_split.messages

            # create object
            DPT.DPObject.create(self, *args, **kwargs)

            # field up object with fields
            # if fixation session, dir == 0
            if not dir:
                # expTime 
                expTime = edf_split.expTime
                # esr
                esr = edf_split.esr

                # trial_timestamps
                time_split = (messages['0_time']).apply(pd.Series)
                time_split = time_split.rename(columns=lambda x: 'time_' + str(x))
                removed = time_split['time_0'].iloc[-1]
                # remove end value from middle column
                time_split['time_0'] = time_split['time_0'][:-1]
                # append removed value to last column
                time_split['time_1'].iloc[-1] = removed
                trial_timestamps = pd.concat(
                    [messages['trialid_time'], time_split['time_0'], time_split['time_1']], axis=1, sort=False)
                trial_timestamps = trial_timestamps.iloc[1:]
                trial_timestamps = trial_timestamps.reset_index(drop=True)
                trial_timestamps = trial_timestamps.fillna(0).astype(int)
            
                # indices
                index_1 = (messages['trialid_time'] - samples['time'].iloc[0]).iloc[1:]
                index_2 = (time_split['time_0'] - samples['time'].iloc[0]).iloc[1:]
                index_3 = (time_split['time_1'] - samples['time'].iloc[0]).iloc[1:]
                indices = pd.concat([index_1, index_2, index_3], axis=1, sort=False)
                indices = indices.fillna(0).astype(int)

                # eye_positions
                eye_pos = samples[['gx_left', 'gy_left']].copy()
                eye_pos['gx_left'][(eye_pos['gx_left'] < 0) | (eye_pos['gx_left'] > self.args['ScreenX'])] = np.nan
                eye_pos['gy_left'][(eye_pos['gy_left'] < 0) | (eye_pos['gy_left'] > self.args['ScreenY'])] = np.nan
                eye_pos = eye_pos[(eye_pos.T != 0).any()]

                sacc_event = pd.DataFrame()
                fix_event = pd.DataFrame()
                fix_times = pd.DataFrame()
                # sacc_event
                new_sacc = events[events['type'] == 'saccade']
                duration = (new_sacc['end'] - new_sacc['start']).reset_index(drop=True)
                sacc_event = pd.concat([sacc_event, duration], axis=1)
                # fix_event
                new_fix = events[events['type'] == 'fixation']
                duration = (new_fix['end'] - new_fix['start']).reset_index(drop=True)
                fix_event = pd.concat([fix_event, duration], axis=1)
                # fix_times
                fix_times = pd.concat([fix_times, new_fix['start'].reset_index(drop=True), new_fix['end'].reset_index(drop=True), duration], axis=1)

                # timestamps
                time_stamps = samples['time']
                time_stamps = time_stamps[time_stamps > 0.0]

                #numSets
                numSets = 1
                # session_start
                session_start = messages['trialid_time'].iloc[1]
                # session_start_index
                session_start_index = session_start - expTime 
                # noOfSessions
                noOfSessions = edf_split.actualSessionNo
                # noOfTrials
                noOfTrials = edf_split.noOfTrials
                # trialcodes
                trial_codes = pd.DataFrame()
                # discrepancies
                discrepancies = []

                self.trial_timestamps = trial_timestamps / esr
                self.indices = indices
                self.calib_eye_pos = eye_pos
                self.numSets = [numSets]
                self.expTime = [expTime / esr]
                self.timestamps = time_stamps / esr
                self.timeouts = edf_split.timeouts / esr
                self.noOfTrials = [noOfTrials]
                self.calib_fix_event = fix_event
                self.calib_fix_times = fix_times / esr
                self.calib_sacc_event = sacc_event
                self.trial_codes = trial_codes
                self.session_start = [session_start / esr]
                self.session_start_index = [session_start_index]
                self.setidx = [0 for i in range(trial_timestamps.shape[0])]
                self.noOfSessions = noOfSessions
                self.samplingRate = esr
                self.discrepancies = discrepancies

            # if it is a navigation session
            else:
                # expTime 
                expTime = edf_split.expTime
                # esr
                esr = edf_split.esr

                sacc_event = pd.DataFrame()
                fix_event = pd.DataFrame()
                fix_times = pd.DataFrame()
                time_stamps = pd.DataFrame()
                eye_pos = pd.DataFrame()

                # saccades
                new_sacc = events[events['type'] == 'saccade']
                sacc_event = (new_sacc['end'] - new_sacc['start']).reset_index(drop=True)
                # fixations
                new_fix = events[events['type'] == 'fixation']
                fix_event = (new_fix['end'] - new_fix['start']).reset_index(drop=True)
                # fixation times
                fix_times = pd.concat([new_fix['start'].reset_index(drop=True), new_fix['end'].reset_index(drop=True), fix_event], axis=1)
                # timestamps
                time_stamps = samples['time'].reset_index(drop=True)

                saccEvent = sacc_event.fillna(0).astype(int)
                fixEvent = fix_event.fillna(0).astype(int)
                fixTimes = fix_times.fillna(0)
                timeStamps = time_stamps.fillna(0)

                # session_start
                session_start = time_stamps.iloc[1]
                
                # session_start_index
                session_start_index = session_start - expTime

                # numSets
                numSets = 1

                # eye positions
                samples['gx_left'][samples['gx_left'] > self.args['ScreenX']] = np.nan
                samples['gx_left'][samples['gx_left'] < 0] = np.nan
                samples['gy_left'][samples['gy_left'] < 0] = np.nan
                samples['gy_left'][samples['gy_left'] > self.args['ScreenY']] = np.nan
                eye_pos = samples[['gx_left', 'gy_left']].reset_index(drop=True)

                # trial_timestamps
                timestamps_1 = messages['trialid_time'] - expTime
                timestamps_2 = messages['Cue_time'] - expTime
                timestamps_3 = messages['End_time'] - expTime
                trial_timestamps = pd.concat(
                    [timestamps_1, timestamps_2, timestamps_3], axis=1, sort=False)
                trial_timestamps = trial_timestamps.iloc[1:]

                # setup for m dataframe by fetching events messages
                # the two parts below merges dataframe columns of start trial, cue offset and end trial
                # by sorting trialid_time in ascending order
                messageEvent = messages[['Trigger', 'Trigger_time', 'trialid ', 'trialid_time', 'Cue', 'Cue_time', 'End', 'End_time', 'Timeout', 'Timeout_time']]

                # trigger versions - reformat output from pyedfread
                trigger_split = messageEvent['Trigger'].apply(pd.Series) # expand Cue column (a list) into columns of separate dataframe
                trigger_split = trigger_split.rename(columns=lambda x: 'trigger_' + str(x)) # rename columns
                messageEvent['Trigger'].loc[~messageEvent['Trigger'].isnull()] = 'Trigger Version ' + trigger_split['trigger_1'].astype(str) # append Cue Offset string to each value

                # cue_offsets
                cue_split = messageEvent['Cue'].apply(pd.Series)
                cue_split = cue_split.rename(columns=lambda x: 'cue_' + str(x)) 
                messageEvent['Cue'].loc[~messageEvent['Cue'].isnull()] = 'Cue Offset ' + cue_split['cue_1'].astype(str) 

                # end_trials
                end_split = messageEvent['End'].apply(pd.Series)
                end_split = end_split.rename(columns=lambda x: 'end_' + str(x))
                messageEvent['End'].loc[~messageEvent['End'].isnull()] = 'End Trial ' + end_split['end_1'].astype(str)

                # timeouts
                timeout_split = messageEvent['Timeout'].apply(pd.Series)
                timeout_split = timeout_split.rename(columns=lambda x: 'time_' + str(x))
                messageEvent['Timeout'].loc[~messageEvent['Timeout'].isnull()] = 'Timeout ' + timeout_split['time_0'].astype(str)

                messageEvent = pd.concat([messageEvent[['Trigger', 'trialid ', 'Cue', 'End', 'Timeout']].melt(value_name='Event'),
                                            messageEvent[['Trigger_time', 'trialid_time', 'Cue_time', 'End_time', 'Timeout_time']].melt(value_name='Time')], axis=1)
                messageEvent = messageEvent[['Time', 'Event']]
                messageEvent = messageEvent.dropna()
                messageEvent = messageEvent.sort_values(by=['Time'], ascending=True) 
                messageEvent = messageEvent.reset_index(drop=True)

                m = messageEvent['Event'].to_numpy()

                s = self.args['TriggerMessage']

                if s != '':
                    sessionIndex = [i for i in range(len(m)) if m[i] == s] # return indices of trigger messages in m
                    noOfSessions = edf_split.noOfSessions # find length of dataframe
                    print('No. of Sessions ', noOfSessions, '\n')

                    extraSessions = 0
                    if noOfSessions > edf_split.actualSessionNo:
                        print('EDF file has extra sessions!')
                        extraSessions = edf_split.actualSessionNo - noOfSessions
                    elif noOfSessions < edf_split.actualSessionNo:
                        print('EDF file has fewer sessions!')

                    #preallocate variables
                    trialTimestamps = np.zeros((m.shape[0], 3*noOfSessions))
                    noOfTrials = 0
                    missingData = pd.DataFrame()
                    sessionFolder = 1

                    # 1) checks if edf file is complete by calling completeData
                    # 2) fills in the trialTimestamps and missingData tables by indexing
                    # with session index (i)

                    i = int(os.getcwd()[-1]) - 1
                    idx = sessionIndex[i]
                    session = self.args['NavDirName'] + str(i + 1)
                    print('Session Name: ', session, '\n')
                    if i == noOfSessions-1:
                        [corrected_times, tempMissing, flag] = completeData(self, events, samples, m[idx:], messageEvent[idx:], session, extraSessions)
                    else:
                        idx2 = sessionIndex[i+1]
                        [corrected_times, tempMissing, flag] = completeData(self, events, samples, m[idx:idx2], messageEvent[idx:idx2], session, extraSessions)
                    if flag == 0:
                        l = 1 + (sessionFolder-1)*3
                        u = 3 + (sessionFolder-1)*3
                        row = corrected_times.shape[0]
                        trialTimestamps[0:row, l-1:u] = corrected_times
                        noOfTrials = corrected_times.shape[0]
                        missingData.append(tempMissing)
                        sessionFolder = sessionFolder + 1
                    else:
                        print('Dummy Session skipped', i, '\n')
                
                else:
                    # some of the early sessions did not have a message indicating the beginning
                    # of the session, so we will have to do something different

                    #preallocate variables
                    noOfSessions = edf_split.actualSessionNo
                    trialTimestamps = np.zeros((m.shape[0], 3*noOfSessions))
                    noOfTrials = 0
                    missingData = pd.DataFrame()
                    sessionFolder = 1
                    sessionIndex = []
                    extraSessions = 0

                    #for i in range(noOfSessions):
                    #session = self.args['NavDirName'] + str(i + 1)
                    #os.chdir(session)

                    # initializing variables for session01
                    if i == 0:
                        sessionIndex = sessionIndex.append(1)
                        nextSessionIndex = 0
                    
                    # load the rplparallel object to find out how many trials there were
                    idx = nextSessionIndex
                    err = 0

                    rplObj = RPLParallel()
                    TrialNum = rplObj.markers.shape
                    TrialNum = TrialNum[0]
                    nextSessionIndex = 3 * TrialNum + idx

                    # look through the messages to figure out which to
                    # skip (aborted sessions)
                    k = nextSessionIndex
                    while ('Start' in m[k] and 'Start' in m[k+1]):
                        err = err + 1
                        k = k + 1
                    
                    # save the session transitions in sessionIndex
                    nextSessionIndex = nextSessionIndex + err

                    if i != noOfSessions:
                        sessionIndex = sessionIndex.append(nextSessionIndex)
                    
                    #os.chdir('..')

                    # Check if eyelink has missing data by calling completeData 
                    if i == noOfSessions-1:
                        [corrected_times, tempMissing, flag] = completeData(self, events, samples, m[idx:], messageEvent[idx:], session, extraSessions)
                    else:
                        idx2 = idx + 3 * TrialNum - 1
                        [corrected_times, tempMissing, flag] = completeData(self, events, samples, m[idx:idx2], messageEvent[idx:idx2], session, extraSessions)
                    if flag == 0:
                        l = 1 + (i-1)*3
                        u = 3 + (i-1)*3
                        row = corrected_times.shape[0]
                        trialTimestamps[0:row, l-1:u] = corrected_times
                        noOfTrials = corrected_times.shape[0]
                        missingData = missingData.append(tempMissing)
                    else:
                        print('Dummy Session skipped', i, '\n')
                    # increase i to go to next sessionFolder
                    i = i + 1

                # edit the size of the array and remove all zero rows and extra columns
                trialTimestamps = trialTimestamps.astype(int)
                trialTimestamps = trialTimestamps[~np.all(trialTimestamps == 0, axis=1), :]
                trialTimestamps = trialTimestamps[:, ~np.all(trialTimestamps == 0, axis=0)]

                # modify number of sessions
                noOfSessions = trialTimestamps.shape[1] // self.args['NumTrialMessages']

                if ~missingData.empty:
                    with open('missingData.csv', 'w', newline='') as file_writer:
                        missingData.to_csv(index=False)

                trial_timestamps = trialTimestamps[~np.all(trialTimestamps == 0, axis=1), :]
                trial_timestamps = trial_timestamps[:, ~np.all(trial_timestamps == 0, axis=0)] # remove zero rows
                trial_timestamps = trial_timestamps - 1
                trial_timestamps = pd.DataFrame(data=trial_timestamps)

                rpl = RPLParallel()

                if rpl.markers.shape == trial_timestamps.shape:
                    markers = rpl.markers
                    trial_codes = pd.DataFrame(data=markers)
                else:
                    raise Exception('markers not consistent')
                
                self.trial_timestamps = trial_timestamps / esr
                self.eye_pos = eye_pos
                self.numSets = [numSets]
                self.expTime = [expTime / esr]
                self.timestamps = time_stamps / esr
                self.timeouts = edf_split.timeouts / esr
                self.noOfTrials = [noOfTrials]
                self.fix_event = fix_event
                self.fix_times = fix_times / esr
                self.sacc_event = sacc_event
                self.trial_codes = trial_codes
                self.session_start = [session_start / esr]
                self.session_start_index = [session_start_index]
                self.setidx = [0 for i in range(trial_timestamps.shape[0])]
                self.noOfSessions = noOfSessions
                self.samplingRate = esr

    def append(self, df):
        # update fields in parent
        DPT.DPObject.append(self, df)

        self.eye_pos = pd.concat([self.eye_pos, df.eye_pos])
        #self.fix_event = pd.concat([self.fix_event, df.fix_event])
        #self.sacc_event = pd.concat([self.sacc_event, df.sacc_event])
        self.calib_eye_pos = pd.concat([self.calib_eye_pos, df.calib_eye_pos])
        self.calib_fix_event = pd.concat([self.calib_fix_event, df.calib_fix_event])
        self.calib_sacc_event = pd.concat([self.calib_sacc_event, df.calib_sacc_event])

        df.trial_timestamps.columns = [0, 1, 2]
        self.trial_timestamps = pd.concat([self.trial_timestamps, df.trial_timestamps], axis=0, ignore_index=True) #, axis=1
        self.numSets.append(df.numSets[0])
        self.expTime.append(df.expTime[0])
        self.timestamps = pd.concat([self.timestamps, df.timestamps])
        self.timeouts = pd.concat([self.timeouts, df.timeouts])
        self.indices = pd.concat([self.indices, df.indices], axis=1)
        self.noOfTrials.append(df.noOfTrials[0])
        self.fix_times = pd.concat([self.fix_times, df.fix_times])
        self.trial_codes = pd.concat([self.trial_codes, df.trial_codes], axis=1)
        self.session_start.append(df.session_start)
        self.session_start_index.append(df.session_start_index)

    def update_idx(self, i):
        return max(0, min(i, len(self.setidx)-1))
        
    def plot(self, i=None, getNumEvents=False, getLevels=False, getPlotOpts=False, ax=None, **kwargs):   
        # set plot options
        plotopts = {'Plot Options': DPT.objects.ExclusiveOptions(['XT', 'XY', 'SaccFixSession', 'SaccFix', 'Discrepancies'], 0), 
                    'SaccFixSessionCutOff': 600}

        if getPlotOpts:
            return plotopts

        # Extract the recognized plot options from kwargs
        for (k, v) in plotopts.items():
            plotopts[k] = kwargs.get(k, v)
        
        plot_type = plotopts['Plot Options'].selected()
        
        session = []

        for index in range(0, self.noOfSessions): # index: 0-4
            session.append([index] * int(self.noOfTrials[index]))
        session = np.array(session).flatten()
        
        if getNumEvents:
            # Return the number of events available
            if plot_type == 'SaccFix':
                return 1, 0
            elif plot_type == 'SaccFixSession':
                #return number of sessions and which session current trial belongs to
                if i is not None:
                    nidx = i
                else:
                    nidx = 0
                return len(self.dirs), nidx
            else:
                if i is not None:
                    nidx = i
                else:
                    nidx = 0
                return len(self.setidx), nidx

        if getLevels:
            # Return the possible levels for this object
            return ['session', 'trial', 'all']

        sidx = 0 # sessidx = int(self.dirs[0][-1]) - 1

        if ax is None:
            ax = plt.gca()


        ax.clear()
        figure = ax.get_figure()
        figure.clf()
        for other_ax in ax.figure.axes:
            other_ax.remove()

        ax = figure.add_subplot(111)

        if plot_type == 'XT':
            if self.dirs[0].endswith('eye'):
                # Fixation of x vs t
                obj_eye_pos = self.calib_eye_pos.to_numpy()
                indices = self.indices.to_numpy()
                y = obj_eye_pos[indices[i][0].astype(int) : indices[i][2].astype(int), :]
                ax.plot(y, 'o-', fillstyle='none')
                lines.Line2D(np.matlib.repmat(obj_eye_pos[indices[i][1].astype(int)], 1, 2), ax.set_ylim())
                
                dir = self.dirs[0]
                subject = DPT.levels.get_shortname("subject", dir)
                date = DPT.levels.get_shortname("day", dir)
                session = DPT.levels.get_shortname("session", dir)
                ax.set_title(subject + date + session)

            else:
                index = 1+(sidx)*3
                x = self.trial_timestamps.to_numpy()[:, index-1:index+2] * self.samplingRate

                obj_timestamps = self.timestamps
                #if len(self.sacc_event.shape) > 1:
                #    obj_timestamps = obj_timestamps.to_numpy()[:, sidx]
                #else:
                obj_timestamps = obj_timestamps.to_numpy()
                    
                trial_start_time = obj_timestamps[x[i][0].astype(int)]
                trial_cue_time = obj_timestamps[x[i][1].astype(int)] - trial_start_time - 0.001
                trial_end_time = obj_timestamps[x[i][2].astype(int)] - 0.001

                data_timestamps = self.get_timestamps(i, x)
                # timestamps is the x axis to be plotted
                timestamps = obj_timestamps[data_timestamps]
                timestamps = timestamps - trial_start_time

                obj_eye_pos = self.eye_pos.to_numpy()
                y = obj_eye_pos[data_timestamps].transpose()

                # plot x axis data
                ax.plot(timestamps, y[:][0], 'b-', linewidth=0.5, label='X position')
                dir = self.dirs[0]
                subject = DPT.levels.get_shortname("subject", dir)
                date = DPT.levels.get_shortname("day", dir)
                session = DPT.levels.get_shortname("session", dir)
                ax.set_title('Eye Movements versus Time - ' + subject + date + session)
                # label axis
                ax.set_xlabel('Time (s)')
                ax.set_ylabel('Position (screen pixels)')
                # plot y axis
                ax.plot(timestamps, y[:][1], 'g-', linewidth=0.5, label='Y position')
                
                # Plotting lines to mark the start, cue offset, and end/timeout for the trial
                ax.plot([0, 0], ax.set_ylim(), 'g', linewidth=0.5)
                ax.plot([trial_cue_time, trial_cue_time], ax.set_ylim(), 'm', linewidth=0.5)
                #trial_end_time = trial_end_time[0]
                timedOut = self.timeouts == trial_end_time
                trial_end_time = trial_end_time - trial_start_time
                timedOut = np.nonzero(timedOut.to_numpy)

                if not timedOut: # trial did not timeout
                    ax.plot([trial_end_time, trial_end_time], ax.set_ylim(), 'r', linewidth=0.5)
                else: # trial did timeout
                    ax.plot([trial_end_time, trial_end_time], ax.set_ylim(), 'b', linewidth=0.5)

                # ax.set_xlim([-0.2, trial_end_time + 0.2]) # set axis boundaries
                ax.legend(loc='best')

        elif plot_type == 'XY':
            if self.dirs[0].endswith('eye'):
                # Calibration - Plot of calibration eye movements
                obj_eye_pos = self.calib_eye_pos.to_numpy() # used to be calib_eye_pos
                indices = self.indices.to_numpy()
                y = obj_eye_pos[indices[i][0].astype(int) : indices[i][2].astype(int), :]
                y = y.transpose()
                ax = plotGazeXY(self, i, ax, y[0], y[1], 'b')
            else:
                # XY - Plots the x and y movement of the eye per trial extract all the trials from one session 
                index = 1+(sidx)*3
                x = self.trial_timestamps.to_numpy()[:, index-1:index+2] * self.samplingRate
                obj_eye_pos = self.eye_pos.to_numpy()
                y = obj_eye_pos[x[i][0].astype(int) : x[i][2].astype(int), :].transpose()
                ax = plotGazeXY(self, i, ax, y[0], y[1], 'b') # plot blue circles

        elif plot_type == 'SaccFix':
            # SaccFix - Histogram of fixations and saccades per session
            if not self.sacc_event.empty:
                sacc_durations = self.sacc_event.to_numpy()
                fix_durations = self.fix_event.to_numpy()

                lower = np.amin(fix_durations)
                upper = np.amax(fix_durations)
                
                edges = np.arange(lower, upper, 25).tolist()
                edges = [x for x in edges if x <= 1000]

                sacc_durations = sacc_durations[sacc_durations != 0]
                fix_durations = fix_durations[fix_durations != 0]

            if not self.calib_sacc_event.empty:
                calib_sacc_durations = self.calib_sacc_event.to_numpy()
                calib_fix_durations = self.calib_fix_event.to_numpy()

                calib_lower = np.amin(calib_fix_durations)
                calib_upper = np.amax(calib_fix_durations)
                
                calib_edges = np.arange(calib_lower, calib_upper, 25).tolist()
                calib_edges = [x for x in calib_edges if x <= 1000]

                calib_sacc_durations = calib_sacc_durations[calib_sacc_durations != 0]
                calib_fix_durations = calib_fix_durations[calib_fix_durations != 0]

            fig = ax.get_figure()
            fig.clf()

            ax1 = fig.add_subplot(211)
            ax1.hist(sacc_durations, density=True, alpha=1, histtype = 'step', bins=edges, label='Saccades: {}'.format(len(sacc_durations)), edgecolor='blue', linewidth=1)
            ax1.hist(fix_durations, density=True, alpha=1, histtype = 'step', bins=edges, label='Fixations: {}'.format(len(fix_durations)), edgecolor='red', linewidth=1)
            fig.text(0.025, 0.5, 'Percentage (%)', va = 'center', rotation = 'vertical')
            plt.setp(ax1.get_xticklabels(), visible=False)
            ax1.legend(loc='best')

            ax2 = fig.add_subplot(212, sharex=ax1)
            ax2.hist(calib_sacc_durations, density=True, alpha=1,  histtype = 'step',  bins=edges, label='Saccades: {}'.format(len(calib_sacc_durations)), edgecolor='green', linewidth=1)
            ax2.hist(calib_fix_durations, density=True, alpha=1,  histtype = 'step', bins=edges, label='Fixations: {}'.format(len(calib_fix_durations)), edgecolor='black', linewidth=1)
            ax2.set_xlabel('Duration (s)')
            ax2.legend(loc='best')
            ax1.set_title('Navigation Sessions')
            ax2.set_title('Fixation Sessions')

        elif plot_type == 'SaccFixSession':
            data = []
            labels = []

            directory = self.dirs[i]
            currSession = DPT.levels.get_shortname('session', directory)
            if currSession == 'seye':
                if not self.calib_sacc_event.empty:
                    calib_sacc = self.calib_sacc_event[self.calib_sacc_event < plotopts['SaccFixSessionCutOff']]
                    calib_fix = self.calib_fix_event[self.calib_fix_event < plotopts['SaccFixSessionCutOff']]

                    data.append(calib_sacc.dropna().to_numpy())
                    data.append(calib_fix.dropna().to_numpy())

            else: 
                if not self.sacc_event.empty:
                    sacc_durations = self.sacc_event[self.sacc_event < plotopts['SaccFixSessionCutOff']]
                    fix_durations = self.fix_event[self.fix_event < plotopts['SaccFixSessionCutOff']]

                    if len(sacc_durations.shape) > 1:
                        data.append(sacc_durations.iloc[:, i].dropna())
                        data.append(fix_durations.iloc[:, i].dropna())

                    else:
                        data.append(sacc_durations.dropna())
                        data.append(fix_durations.dropna())

            labels.append('Saccades')
            labels.append('Fixations')
            ax.boxplot(data, notch=True, labels=labels)
            subject = DPT.levels.get_shortname("subject", directory)
            date = DPT.levels.get_shortname("day", directory)
            ax.set_title('Saccades and Fixations For Session - ' + subject + date + currSession)
            ax.set_ylabel('# of events')

        elif plot_type == 'Discrepancies':
            # plot the distributions of the durations in ms
            discrepancies = self.discrepancies.reshape((self.discrepancies.shape[0]*3, 1))
            ax.hist(discrepancies, bins=50, density=False, alpha=0.5, color='#31b4e8', edgecolor='black', linewidth=0.3)
            ax.set_title('Histogram for rplparallel and eyelink durations')
            ax.set_xlabel('s')
            ax.set_ylabel('occurence')

        return ax      
    
    def get_timestamps(self, i, x):
        if i == 0:
            data_timestamps = np.arange(0, x[i+1][0].astype(int))
        elif i != x.shape[0]-1:
            data_timestamps = np.arange(x[i-1][2], x[i+1][0]).astype(int)
        else:
            data_timestamps = np.arange(x[i-1][2], len(self.timestamps)-1).astype(int)
            
        return data_timestamps


# plotGazeXY helper method to plot gaze position. Uses matlab's plot function
def plotGazeXY(self, i, ax, gx, gy, lineType):
    ax.scatter(gx, gy, color='none', edgecolor=lineType)
    ax.invert_yaxis() # reverse current y axis

    #currentAxis = ax.gca() # draw rect to represent the screen
    ax.add_patch(patches.Rectangle((0, 0), self.args['ScreenX'], self.args['ScreenY'], fill=None, alpha=1, lw=0.5))

    dir = self.dirs[0]
    subject = DPT.levels.get_shortname("subject", dir)
    date = DPT.levels.get_shortname("day", dir)
    session = DPT.levels.get_shortname("session", dir)
    ax.set_title('Eye movements - ' + subject + date + session)
    ax.set_xlabel('Gaze Position X (screen pixels)')
    ax.set_ylabel(('Gaze Position Y (screen pixels)'))

    return ax
  
def completeData(self, events, samples, m, messageEvent, sessionName, moreSessionsFlag):
    # set default flag to 0
    flag = 0
    corrected_times = []
    tempMissing = []

    # the start of the experiment is taken to normalise the data 
    expTime = int(samples['time'].iloc[0] - 1)

    # correct the data for one session
    # create a new matrix that contains all trial messages only
    m = m[m != 'Trigger Version 84']
    messages = m

    # store starting times of all events
    eltimes = messageEvent['Time']

    # read rplparallel file
    rpl = RPLParallel()

    if (rpl.numSets != 0 and rpl.timeStamps.shape[0] != 1):  #no missing rplparallel.mat
        # markers will store all the event numbers in the trial, as taken from the ripple object. 
        # This will be used to mark which events are missing in the eyelink object. 
        # (1-start, 2-cue, 3/4 - end/timeout)
        markers = rpl.markers # get info from rplparallel hdf5
        rpltimeStamps = rpl.timeStamps
        n = len(markers)

        # Check if the rplparallel object is formatted correctly or is missing information
        if n == 1: # if the formatting is 1xSIZE
            df = rpl
            rpl_obj = RPLParallel(saveLevel=1, Data=True, markers=df.markers, timeStamps=df.timeStamps, rawMarkers=df.rawMarkers, trialIndices=df.trialIndices, sessionStartTime=df.sessionStartTime) 
            rpl_filename = rpl_obj.get_filename()

            markers = np.delete(markers, 0)
            rpltimeStamps = np.delete(rpltimeStamps, 0)
            rpltimeStamps = np.delete(rpltimeStamps, rpltimeStamps[np.nonzero(markers == 0)]) # rpltimeStamps(find(~markers)) = [];
            markers = np.delete(markers, np.nonzero(markers == 0))
            n = len(markers) / 3

            if len(markers) % 3 != 0:
                markers = pd.DataFrame(rpl.markers)
                rpltimeStamps = pd.DataFrame(rpl.timeStamps)
                [markers, rpltimeStamps] = callEyelink(self, markers, m, eltimes - expTime, rpltimeStamps)
            else: 
                markers = markers.reshape([3, n])
                rpltimeStamps = rpltimeStamps.reshape([3, n])
                markers = markers.transpose()
                rpltimeStamps = rpltimeStamps.transpose()
            n = markers.shape[0]
            rpl_obj = RPLParallel(saveLevel=1, Data=True, markers=markers, timeStamps=rpltimeStamps, rawMarkers=df.rawMarkers, trialIndices=df.trialIndices, sessionStartTime=df.sessionStartTime)

        elif n * 3 < m.shape[0]: # If rplparallel obj is missing data, use callEyelink
            files = os.listdir()
            count = 0
            for file in files:
                if file.startswith('rplparallel'):
                    count = count + 1 
            if count == 0:
                df = rpl # extract all fields needed to go into rplparallel constructor
                [markers, rpltimeStamps] = callEyelink(self, markers, m, eltimes-expTime, rpltimeStamps)
                # save object and return
                n = markers.shape[0]
                rpl_obj = RPLParallel(saveLevel=1, Data=True, markers=markers, timeStamps=rpltimeStamps, rawMarkers=df.rawMarkers, trialIndices=df.trialIndices, sessionStartTime=df.sessionStartTime)

        noOfmessages = messages.shape[0] # stores the number of messages recorded by eyelink in the session

        missing = np.zeros((n, markers.shape[1])) #stores the event that is missing
        rpldurations = np.zeros((n, markers.shape[1])) #stores the rpl durations for filling missing eyelink timestamps
        elTrials = np.zeros((n, markers.shape[1])) #stores the eyelink timestamps for the events in a trial

        # To check if there is more sessions than must be
        if moreSessionsFlag != 0:
            if (n * 3) - messageEvent.shape[0] - 2 >= 100: # use of len of messageEvent, check if the same
                flag = 1
                # create empty dataframes
                elTrials = np.zeros((n, 3)) # pd.DataFrame(columns=range(0,3), index=range(0,n))
                missingData = pd.DataFrame(columns = ['Type', 'Timestamps', 'Messages'], index=range(0,n))
                return
        
        # calculate the durations between rplparallel timestamps 
        # rpldurations(0,0) is assumed to be the time difference between the
        # start of the session and the trial start time
        rpldurations[:, 0] = np.insert(rpltimeStamps[1:len(rpltimeStamps), 0] - rpltimeStamps[0:len(rpltimeStamps)-1,2], 0, rpltimeStamps[0,0], axis=0)
        rpldurations[:, 1] = rpltimeStamps[:, 1] - rpltimeStamps[:, 0] # cue time - start time
        rpldurations[:, 2] = rpltimeStamps[:, 2] - rpltimeStamps[:, 1] # end time - cue time

        idx = 1
        n = n * 3 # size of markers
        newMessages = np.zeros((n, 1)) # pd.DataFrame(columns=[0], index=range(0,n)) # stores all the missing messages

        # For loop that goes through the entire rplparallel markers matrix
        # (1) Checks if edf message markers are missing, and accordingly
        # corrects the missing time using the rpldurations
        # (2) ensures that missing trials common to eyelink and rplparallel
        # are deleted
        # (3) creates the missing array that is later addded to the
        # missingData table
        [elTrials, missing, newMessages] = filleye(self, messages, eltimes, rpl)

        # get rid of extra zeros
        [row, _] = np.where(elTrials == 0)
        elTrials = np.delete(elTrials, row, 1)
        n = np.count_nonzero(missing)

        if n != 0: # if there are missing messages in this session, make the missingData matrix to add to the .csv file 
            print('Missing messages')
            type = np.empty((n, 1))
            type.fill(24)
            correctedTimes = elTrials[np.where(missing != float(0))[0][0], np.where(missing != float(0))[1][0]]
            newMessages = newMessages.dropna()
            missingData = pd.DataFrame()
            missingData['Type'] = type[0]
            missingData['Timestamps'] = correctedTimes
            missingData['Messages'] = newMessages
        else: #if there are not any missing messages, make the missingData matrix empty 
            print('No missing messages')
            missingData = pd.DataFrame(columns = ['Type', 'Timestamps', 'Messages'], index=range(0,n))
        
        # To ensure that the correction of the eyelink object went correctly, 
        # we now plot a histogram of the discrepancies in the start-cue,
        # cue-end and end-start durations for ripple and eyelink objects for
        # the same session to ensure that the data recorded is consistent 
        eldurations = np.empty((elTrials.shape[0], 3))
        elTrials = elTrials - expTime
        eldurations[:, 0] = np.insert(elTrials[1:, 0] - elTrials[0:len(elTrials)-1, 2], 0, 0, axis=0)
        eldurations[:, 1] = elTrials[:, 1] - elTrials[:, 0] # cue time - start time
        eldurations[:, 2] = elTrials[:, 2] - elTrials[:, 1] # end - cue time
        eldurations = eldurations / 1000 #conversion to seconds
        discrepancies = abs(rpldurations - eldurations) # stores the discrepancy between the two times in seconds
        discrepancies[0, 0] = 0
        self.discrepancies = discrepancies
        
    else: #missing rplparallel  
        # assume that there are no missing messages
        # os.chdir('..')
        print('Empty object. Just fill up time array\n')
        n = messages.shape[0]

        elTrials = np.zeros((n, 3)) # stores the eyelink timestamps for the events in a trial
        missing = np.zeros((n, 3))

        for i in range(n):
            r = math.floor(i / 3) + 1 # row
            c = i % 3

            if c == 0:
                r = r - 1
                c = 3
            
            missing[r, c] = 0
            if 'Start Trial' in messages[i, 0]:
                elTrials[r, 0] = eltimes[i, 0] - expTime
            elif 'End Trial' in messages[i, 0]:
                elTrials[r, 2] = eltimes[i, 0] - expTime
            elif 'Timeout' in messages[i, 0]:
                elTrials[r, 2] = eltimes[i, 0] - expTime
            elif 'Cue Offset' in messages[i, 0]:
                elTrials[r, 1] = eltimes[i, 0] - expTime

        print('No missing messages')
        missingData = pd.DataFrame(columns = ['Type', 'Timestamps', 'Messages'], index=range(0,n))

    return elTrials, missingData, flag

def filleye(self, messages, eltimes, rpl):
    eyelink_raw = np.empty((1,len(messages)))
    eyelink_raw[:] = np.nan

    for i in range(len(messages)):
        full_text = messages[i]
        full_text = full_text.split() # splits string into list
        full_text = full_text[len(full_text)-1]
        eyelink_raw[0, i] = float(full_text)

    eye_timestamps = eltimes.to_numpy().transpose()
    truth_timestamps = rpl.timeStamps
    truth_timestamps = truth_timestamps * 1000
    truth = rpl.markers

    # data transformed into format used by function
    split_by_ones = np.empty((2000,10))
    split_by_ones[:] = np.nan
    row, col, max_col, start = 1, 1, 1, 1

    for i in range(eyelink_raw.shape[1]): # naively splits the sequence by plausible triples by cue onset
        if (eyelink_raw[0, i] < 20 and eyelink_raw[0, i] > 9) or col > 3:
            row = row + 1
            if col > max_col:
                max_col = col
            col = 1
        elif col != 1:
            if base < 20:
                if eyelink_raw[0, i] != base + 10:
                    if eyelink_raw[0, i] != base + 20:
                        if eyelink_raw[0, i] != base + 30:
                            row = row + 1
                            col = 1
            elif base < 30:
                if eyelink_raw[0, i] != base + 10:
                    if eyelink_raw[0, i] != base + 20:
                        row = row + 1
                        col = 1
            else:
                row = row + 1
                col = 1

        split_by_ones[row, col] = eyelink_raw[0, i]
        base = eyelink_raw[0, i]
        col = col + 1
        if (start == 1):
            start = 0

    if np.sum(~np.isnan(split_by_ones[0,:])) != 0:
        split_by_ones = split_by_ones[1:row+1, 1:max_col]
    else:
        split_by_ones = split_by_ones[2:row+1, 1:max_col]
    
    arranged_array = np.empty((split_by_ones.shape))
    arranged_array[:] = np.nan
    
    for row in range(split_by_ones.shape[0]):
        for col in range(3):
            if np.isnan(split_by_ones[row, col]):
                break
            if split_by_ones[row, col] < 20:
                arranged_array[row, 0] = split_by_ones[row, col]
            elif split_by_ones[row, col] < 30:
                arranged_array[row, 1] = split_by_ones[row, col]
            else:
                arranged_array[row, 2] = split_by_ones[row, col]

    missing_rows = len(truth) - len(arranged_array)

    # print(truth)
    # print(arranged_array.shape) # correct

    slice_after = np.empty((missing_rows, 2)) # this section accounts for triples that look ok, but are made of two trials with the same posters
    slice_after[:] = np.nan
    slice_index = 1

    for row in range(arranged_array.shape[0]):
        #if (row > 316):
        #    print('debugger')
        if ~np.isnan(arranged_array[row, 0]):
            if ~np.isnan(arranged_array[row, 1]):
                tmp = arranged_array.transpose()
                tmp = tmp.flatten('F')
                idx = np.sum(~np.isnan(tmp[0:3*(row)+1]))
                td = eye_timestamps[idx+1] - eye_timestamps[idx]

                rpl_chunk = truth_timestamps[row:min(max(row, row+missing_rows+1), truth_timestamps.shape[0]), 0:2]
                rpl_chunk_flag = truth[row:min(max(row, row+missing_rows+1), truth_timestamps.shape[0]), 0:2]
                
                rpl_chunk = rpl_chunk[rpl_chunk_flag[:, 0] == arranged_array[row, 0], :]
                rpl_td = rpl_chunk[:, 1] - rpl_chunk[:, 0]

                if np.min(abs(rpl_td - td)) > 1500:
                    slice_after[slice_index, :] = [row, 0]
                    slice_index = slice_index + 1

            elif ~np.isnan(arranged_array[row, 2]):
                tmp = arranged_array.transpose()
                tmp = tmp.flatten('F')
                idx = np.sum(~np.isnan(tmp[0:3*(row)+1]))
                idx3 = np.sum(~np.isnan(tmp[0:3*(row)+3]))
                td = eye_timestamps[idx3] - eye_timestamps[idx]

                rpl_chunk = truth_timestamps[row:min(max(row, row+missing_rows+1), truth_timestamps.shape[0]), 0:3]
                rpl_chunk_flag = truth[row:min(max(row, row+missing_rows+1), truth_timestamps.shape[0]), 0:3]

                rpl_chunk = rpl_chunk[rpl_chunk_flag[:,0] == arranged_array[row,0], :]
                rpl_td = rpl_chunk[:,2] - rpl_chunk[:,0]

                if np.min(abs(rpl_td - td)) > 1500:
                    slice_after[slice_index, :] = [row, 0]
                    slice_index = slice_index + 1

        elif ~np.isnan(arranged_array[row, 1]):
            if ~np.isnan(arranged_array[row, 2]):
                tmp = arranged_array.transpose()
                tmp = tmp.flatten('F')
                idx = np.sum(~np.isnan(tmp[0:3*(row)+2]))
                td = eye_timestamps[idx+1] - eye_timestamps[idx]

                rpl_chunk = truth_timestamps[row:min(max(row, row+missing_rows+1), truth_timestamps.shape[0]), 1:3]
                rpl_chunk_flag = truth[row:min(max(row, row+missing_rows+1), truth_timestamps.shape[0]), 1:3]
                
                rpl_chunk = rpl_chunk[rpl_chunk_flag[:,1] == arranged_array[row,1], :]
                rpl_td = rpl_chunk[:,1] - rpl_chunk[:,0]

                if np.min(abs(rpl_td - td)) > 1500:
                    slice_after[slice_index, :] = [row, 0]
                    slice_index = slice_index + 1

    slice_after = slice_after[0:slice_index-1,:]
    empty_missing_rows = np.empty((missing_rows, 3))
    empty_missing_rows[:] = np.nan
    arranged_array = np.vstack((arranged_array, empty_missing_rows))

    if len(slice_after) != 0:
        for slice in range(len(slice_after), -1, -1): # slices according to previously identified segments
            new_array = np.empty(np.shape(arranged_array)) # can I use len or shape
            new_array[0:slice_after[slice, 0]-1, :] = arranged_array[0:slice_after[slice, 0]-1, :] # is it [0:slice_after[slice,0]-2,:] , variables start at 0
            new_array[slice_after[slice, 0]-1, 0:slice_after[slice, 1]] = arranged_array[slice_after[slice, 0], 0:slice_after[slice,1]] 
            new_array[slice_after[slice, 0], slice_after[slice, 1]:3] = arranged_array[slice_after[slice, 0]-1,slice_after[slice,1]:3]
            arranged_arrya[slice_after[slice, 0]:arranged_array.shape[0], :]
            new_array[slice_after[slice, 0]+1:, :] = arranged_array[slice_after[slice,0]:arranged_array.shape[0]-1,:]    
            arranged_array = new_array
            missing_rows = missing_rows - 1

    for row in range(missing_rows): #this segment attempts to identify where entire trials may have gone missing, by comparing with rpl timings
        error = np.nansum(truth - arranged_array, axis=1) #nansum(dim=2)
        error_index = np.min(error.nonzero())
        if np.sum(abs(error)) == 0:
            break
        if error_index == 0:
            empty_nan = np.empty((1, 3))
            empty_nan[:] = np.nan
            arranged_array = np.vstack((empty_nan, arranged_array[0:len(arranged_array)-1, :]))
        else:
            for col in range(3):
                if ~np.isnan(arranged_array[error_index-1, col]):
                    pre_id = arranged_array[error_index-1, col] % 10
                    break
                # identity of preceeding trial determined
            # looking up how many trials before this have the same identity
            count = 0
            while (1):
                if error_index-1-count == 0:
                    break
                for col2 in range(3):
                    if ~np.isnan(arranged_array[error_index-1-count, col2]):
                        pre_id_check = arranged_array[error_index-1-count, col2] % 10
                        break
                if pre_id_check != pre_id:
                    break
                if error_index-2-count == 0:
                    break
                count = count + 1
                     
            # count now stores the number of repeated posters before the
            # misalignment has been detected (need to test all possible
            # locations).
            print('count', count)

            eye_start_trials = np.empty((count+2, 1))
            eye_start_trials[:] = np.nan
            eye_start_count = 0

            esi = 0
            for r in range(arranged_array.shape[0]):
                for c in range(3):
                    if ~np.isnan(arranged_array[r, c]):
                        esi = esi + 1
                    if (r >= error_index-count-1) and (r <= error_index):
                        if c == 0:
                            if ~np.isnan(arranged_array[r, c]):
                                eye_start_trials[eye_start_count, 0] = eye_timestamps[esi]
                            elif ~np.isnan(arranged_array[r, c+1]):
                                print('taking cue offset and cutting 2 seconds to estimate start trial timing')
                                eye_start_trials[eye_start_count, 0] = eye_timestamps[esi+1]-2000
                            else:
                                print('taking end trial and cutting 10 seconds to estimate start trial timing')
                                eye_start_trials[eye_start_count, 0] = eye_timestamps[esi+1]-10000
                            eye_start_count = eye_start_count + 1
                
            rpl_start_trials = truth_timestamps[error_index-count-1:error_index+1, 0]
            diff_eye = np.diff(eye_start_trials.flatten())
            diff_rpl = np.diff(rpl_start_trials)
            discrepancy = diff_eye - diff_rpl

            row_to_insert = np.where(discrepancy == np.amax(discrepancy))
            row_to_insert = row_to_insert[0][0]+2
            empty_nans = np.zeros((1,3))
            empty_nans[:] = np.nan

            arranged_array = np.vstack((arranged_array[0:error_index-count-2+row_to_insert, :], empty_nans, arranged_array[error_index-count-2+row_to_insert:len(arranged_array), :]))
            arranged_array = arranged_array[0:len(arranged_array)-1, :]
    
    if np.nansum(abs(arranged_array.astype(float) - truth.astype(float))) > 0:
        raise ValueError('eyelink was not properly arranged. current arrangement still clashes with ripple')

    missing = truth*np.isnan(arranged_array).astype(float)

    newMessages = pd.DataFrame(index=range(3*truth.shape[0]), columns=range(1))
    flat_truth = truth.transpose()
    flat_truth = flat_truth.flatten('F')
    flat_truth_time = truth_timestamps.transpose()
    flat_truth_time = flat_truth_time.flatten('F')
    flat_eye = arranged_array.transpose()
    flat_eye = flat_eye.flatten('F')
    flat_truth = flat_truth*np.isnan(flat_eye).astype(float)

    for i in range(len(flat_truth)):
        if flat_truth[i] != 0:
            if flat_truth[i] < 20:
                text = 'Start Trial ' + str(flat_truth[i].astype(int))
                newMessages.loc[i] = text
            elif flat_truth[i] < 30:
                text = 'Cue Offset ' + str(flat_truth[i].astype(int))
                newMessages.loc[i] = text
            elif flat_truth[i] < 40:
                text = 'End Trial ' + str(flat_truth[i].astype(int))
                newMessages.loc[i] = text
            else:
                text = 'Timeout ' + str(flat_truth[i].astype(int))
                newMessages.loc[i] = text
    # ready for output

    elTrials = np.zeros((1, 3*missing.shape[0])) # change to empty list
    counter = 1
    eltimes = eltimes.to_list()

    for i in range(len(flat_eye)):
        if ~np.isnan(flat_eye[i]):
            elTrials[0][i] = eltimes[counter]
            counter = counter + 1

    elTrials = elTrials.astype(int)

    for i in range(len(elTrials[0])):
        if elTrials[0][i] == 0:
            if i == 1:
                inv_delta = flat_truth_time[i+1] - flat_truth_time[i]
                elTrials[0][i] = (elTrials[0][i+1] - inv_delta).round()
                print('shouldnt see nans here')
            else:
                delta = flat_truth_time[i] - flat_truth_time[i-1]
                elTrials[0][i] = (elTrials[0][i-1] + delta).round()
                print('shouldnt see nans here')

    elTrials = elTrials.reshape([len(elTrials[0])//3, 3]) # ready for output
    return elTrials, missing, newMessages

def callEyelink(self, markersRaw, messages, eltimes, rpltimeStamps):
    # stores timestamps from eyelink
    eldurations = np.insert(eltimes[1:] - eltimes[0:len(elTrials)-1], 0, 0, axis=0)
    eldurations = eldurations / 1000
    eltimes = eldurations

    # Get rid of the 0s that separate the markers and the first 84 markers 
    # Do the same for the rplparallel timestamps to reconstruct them.
    if (markersRaw[0] == 84):
        markersRaw = markersRaw.pop() # remove first element from list
        rpltimeStamps = rpltimeStamps.pop()
    rpltimeStamps = np.delete(rpltimeStamps, rpltimeStamps[np.nonzero(markers == 0)])
    markers = np.delete(markers, np.nonzero(markers == 0))
    n = markersRaw.shape[1]

    if (n < messages.shape[0]): # messages = m # should be len(messages)
        m = messages.shape[0] 

        # first check if edf file is missing something too
        remainder = m % 3
        if (remainder != 0):
            print('Edf file incomplete\n')
        
        markersNew = np.zeros((m, 1))
        timesNew = np.zeros((m, 3))
        print(markersNew)
        print(timesNew)
        idx = 1
        idx2 = 1
        sz = m + n
        count = 1

        for i in range(sz):
            # convert to row-column indexing for markersNew
            r = math.floor(i / 3) + 1 # row
            c = i % 3 # column
            
            if (c == 0):
                r = r - 1
                c = 3

            if (idx2 <= m): #prevent accessing more than the array size 
                # Convert the string to a number for easier manipulation
                message = ''.join(str(e) for e in messages[idx2, 0]) # convert to string
                message = int(message[len(message)-5:len(message)-2])
            
            if ((math.floor(message / 10) == c) or (math.floor(message / 10) == 4) and c == 3): #ensures that messages itself isn't missing a trial
                if (idx <= n and message == markersRaw[0, idx]): # if the marker exists in rplparallel
                    markersNew[r, c] = markersRaw[0, idx]
                    timesNew[r, c] = rpltimeStamps[0, idx]
                    idx = idx + 1
                else: # rplparallel is missing a marker
                    print('Missing in rplparallel but found in messages\n')
                    if (c == 1 and r != 1):
                        timesNew[r, c] = timesNew[r-1, 2] + eltimes[idx2, 0]
                    elif (c == 1 and r == 1):
                        timesNew[r, c] = rpltimeStamps[0, idx] - eltimes[idx2+1, 0] # maybe dont need +1 in python
                    else:
                        timesNew[r, c] = timesNew[r, c-1] + eltimes[idx2, 0]
                idx2 = idx2 + 1
            else: #check if markersRaw has it instead 
                if ((math.floor(markersRaw[0, idx] / 10) == 3) or (math.floor(markersRaw[0, idx] / 10) == 4 and c == 3)):
                    if (c != 1 and ((markersRaw[0, idx] % 10) == (markersRaw[0, idx - 1] % 10))):
                        markersNew[r, c] = markersRaw[0, idx]
                        timesNew[r, c] = rpltimeStamps[0, idx]
                        print('Missing Data from messages. but found in rplparallel\n')
                        disp([r, c])
                else:
                    markersNew[r, c] = 0
                    timesNew[r, c] = 0
                    print('Use unitymaze\n')
                    count = count + 1
                idx = idx+1
            
            # once done checking
            if (idx > n and idx2 > m):
                break;
    else:
        m = messages.shape[0]
        markersNew = np.zeros((n+m, 3))
        timesNew = np.zeros((n+m, 3))
        idx = 1 # parsing through markers
        idx2 = 1 # parsing through messages
        count = 0
        sz = n + m

        for i in range(sz):
            # index for markersNew
            r = math.floor(i / 3) + 1 # row
            c = i % 3 # column
            
            if (c == 0):
                r = r - 1
                c = 3

            if (idx2 <= m): 
                message = ''.join(str(e) for e in messages[idx2, 0]) # convert to string
                message = int(message[len(message)-5:len(message)-2])
            
            if (math.floor(markersRaw[0, idx] / 10) == c): #if it is going in the correct column
                if (idx2 <= m and message == markersRaw[0, idx]): #if messages has it we can move ahead
                    idx2 = idx2 + 1
                else:
                    count = count + 1
                markersNew[r, c] = markersRaw[0, idx]
                timesNew[r, c] = rpltimeStamps[0, idx]
                idx = idx + 1
            elif ((math.floor(markersRaw[0, idx] / 10) == 4) and c == 3): #timeout condition
                if (idx2 <= m and message == markersRaw[0, idx]):
                    idx2 = idx2 + 1      
                markersNew[r, c] = markersRaw[0, idx]
                timesNew[r, c] = rpltimeStamps[0, idx]
                idx = idx + 1
            else: # it is missing from rplparallel
                # check if messages has it
                if ((math.floor(message / 10) == c) or (math.floor(message / 10) == 4) and c == 3): # message has it
                    print('Missing in rplparallel. But found in messages\n')
                    markersNew[r, c] = message
                    if (c == 1):
                        timesNew[r, c] = timesNew[r-1, 2] + eltimes[idx2, 0]
                    else:
                        timesNew[r, c] = timesNew[r, c-1] + eltimes[idx2, 0]
                    idx2 = idx2 + 1
                else: # even messages doesnt have it
                    print('Delete Trial\n')
                    markersNew[r, c] = 0
                    timesNew[r, c] = 0
                    count = count + 1
            # to ensure that we can break from the loop and don't need to waste execution time 
            if (idx > n and idx > m):
                break
    
    markersNew = markersNew[np.any(markersNew, 2)][:]
    timesNew = timesNew[np.any(timesNew, 2)][:]
    print(count)

    return markersNew, timesNew
