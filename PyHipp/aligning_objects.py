# This function reads the three objects (eyelink, unityfile, rplparallel)
# and aligns the timings between each marker (cue on to cue off, cue off to
# end trial), to match that of rplparallel. This is done by scaling
# individaul timepoints between markers for both unityfile and eyelink 
# to make the sum identical to that of rplparallel. For unityfile, large
# discrepencies between total trial times (end - cue onset) compared to
# rplparallel will result in all individual timestamps between the markers
# being set to the first timestamp (flattened).
#
# for comparing time between trial start and end (rpl third column - first
# column), take indices from unityTrigger (eg. 50 261). This refers to data
# indices in unityData, which records time since previous sample. Hence, 
# duration for trial can be found by summing 51st to 261st items in
# unityData. It also corresponds to subtracting 51st row from 262nd row in
# unityTime.
#
# To be run from the session directory, specifying discrepency threshold in
# seconds (defaults to 0.02s or 20ms).

import h5py
import time
import numpy as np
import numpy.matlib
import pandas as pd
import hickle as hkl
import DataProcessingTools as DPT
from .rplparallel import RPLParallel
from .eyelink import Eyelink
from .unity import Unity



def aligning_objects():
    threshold = 0.02

    uf = Unity()
    rp = RPLParallel()
    el = Eyelink()
    
    # check if triplets are aligned already
    if round(rp.timeStamps[0][0],1) == round(el.timestamps[el.trial_timestamps[0][0]*1000],1) and rp.timeStamps[0][0] == uf.timeStamps[0][0][0]:
        print('objects have already been aligned, exiting...')
        return    
    
    #%% convert to sample point units by multiplying with samplingRate
    el.session_start[0] = el.session_start[0]*el.samplingRate
    el.timestamps = el.timestamps*el.samplingRate
    el.trial_timestamps = el.trial_timestamps*el.samplingRate
    el.fix_times = el.fix_times*el.samplingRate
    el.timestamps = el.timestamps[el.timestamps > 0]
            
    #%% make data into column vector
    true_timestamps = np.array(rp.timeStamps) * 1000  # convert to seconds
    a = np.shape(true_timestamps)
    true_timestamps = np.reshape(true_timestamps,a[0]*a[1],order='C')
    
    el_trial_timestamps_flat = np.array(el.trial_timestamps)
    b = np.shape(el_trial_timestamps_flat)
    el_trial_timestamps_flat = np.reshape(el_trial_timestamps_flat,b[0]*b[1],order='C')
    
    uf_unityTriggers_flat = uf.unityTriggers[0]
    c = np.shape(uf_unityTriggers_flat)
    uf_unityTriggers_flat = np.reshape(uf_unityTriggers_flat,c[0]*c[1],order='C')
    
    #%% make the two three columns of el.fix_times into column vector
    saving_closest_fix_times = np.array(el.fix_times)
    saving_closest_fix_times = saving_closest_fix_times[:,0:2]
    saving_closest_fix_times = np.transpose(saving_closest_fix_times)
    saving_closest_fix_times = np.reshape(saving_closest_fix_times,(np.shape(saving_closest_fix_times)[0]*np.shape(saving_closest_fix_times)[1]),order='F')
    
    #%% reasign saving_closest_fix_times to the index value when ts(eyelink timestamps) is larger it
    ts = np.array(el.timestamps)
    t = time.time()
    
    difference = float('NaN')
    index = 0    
    for stamps in range(np.shape(ts)[0]):
        if np.isnan(difference):
            difference = ts[stamps] - saving_closest_fix_times[index]    
        else:
            if ts[stamps] - saving_closest_fix_times[index] > 0 :
                if abs(difference) > (abs(ts[stamps]) - saving_closest_fix_times[index]):
                    saving_closest_fix_times[index] = stamps
                else:
                    saving_closest_fix_times[index] = stamps - 1
                difference = float('NaN')
                index = index + 1
            else:
                difference = ts[stamps] - saving_closest_fix_times[index]
                
        if index >= np.shape(saving_closest_fix_times)[0]:
            break
    
    # reshape saving_closest_fix_times back to 2 columns
    saving_closest_fix_times = np.reshape(saving_closest_fix_times,(int(np.shape(saving_closest_fix_times)[0]/2),2))
    saving_closest_fix_times += 1
    elapsed = time.time() - t
    print("{time:.2f} taken for reassigning closest_fix_times".format(time=elapsed))
    
    #%% check on rplparallel timestamps
    dubious_counter = 0
    dubious_collector = []  
    for j in range(np.shape(true_timestamps)[0]-1):  # do we need to do so many shifting?
        # based on rplparallel
        true_start = true_timestamps[j]  # in sample point
        true_end = true_timestamps[j+1]
        true_diff = true_end - true_start

        # based on eyelink
        current_start = el_trial_timestamps_flat[j]  # in sample point, starting from 1
        current_end = el_trial_timestamps_flat[j+1]
        current_chunk = np.array(el.timestamps)  # in sample point, strating from cpu time
        current_chunk = current_chunk[int(current_start)-1:int(current_end)]
        current_chunk = current_chunk.astype(float)
        current_diff = current_chunk[-1] - current_chunk[0]
        
        # fix eyelink timestamps
        current_start_time = current_chunk[0]
        current_end_time = current_chunk[-1]
        current_chunk = (current_chunk - current_start_time)* true_diff/current_diff  # now scaled to rpl timing  
        current_chunk = current_chunk + current_start_time  # shifted back to original start
        shifting_needed = current_chunk[-1] - current_end_time  # finds how much every subsequent timepoints need to shift by to fix gap for next two points
    
        el.timestamps[int(current_start)-1:int(current_end)] = np.uint32(current_chunk)
        el.timestamps[int(current_end):] += +shifting_needed  # every subsequent timepoints shifted to compensate for earlier compression/expansion
    
        # fix unity timestamps
        true_diff = true_diff/1000  # diff from rpl in seconds, for comparison with unityfile timings
        
        current_start = uf_unityTriggers_flat[j]+2
        current_end = uf_unityTriggers_flat[j+1]+2
        current_chunk = uf.unityTime[0][current_start-1:current_end]
        current_diff = current_chunk[-1] - current_chunk[0]
        current_start_time = current_chunk[0]
        current_end_time = current_chunk[-1]

        
        dubious = 0
        if j % 3 == 0:
            discrep = current_diff - true_diff
            #print(j/3)
            #print(discrep)
        elif j % 3 == 1:
            discrep = discrep + current_diff - true_diff;
            #print(discrep)
        else:
            if abs(discrep) > threshold:
                dubious = 1       
        
        current_chunk = (current_chunk - current_start_time) * true_diff/current_diff  # now scaled to rpl timing  
        current_chunk = current_chunk + current_start_time  # shifted back to original start
        shifting_needed = current_chunk[-1] - current_end_time  # finds how much every subsequent timepoints need to shift by to fix gap for next two points
        
    
        uf.unityTime[0][int(current_start)-1:int(current_end)] = current_chunk
        uf.unityTime[0][int(current_end):] += shifting_needed  # every subsequent timepoints shifted to compensate for earlier compression/expansion
        
        
        if dubious == 1:
            prev_prev_start = uf_unityTriggers_flat[j-2]+1
            chunk_size = np.shape(uf.unityTime[0][prev_prev_start:current_start])[0]
            uf.unityTime[0][prev_prev_start:current_start] = numpy.matlib.repmat(uf.unityTime[0][prev_prev_start],1,chunk_size)  # because the trial duration in uf differs too much from that of rpl, we mark this trial as unusable by setting all but the last value to the initial value (last value not changed, so that next trial can be evaluated).
            
            dubious_counter = dubious_counter + 1
            dubious_collector.append(j)
            print('but disparity between rpl and unity was quite large')
            print(discrep)
   
    
    print('dubious counter: ' + str(dubious_counter))
    print('dubious location(s): ' + str(dubious_collector))
    
    markers = np.array(rp.rawMarkers)
    
    #%% shifting all to reference 0 as ripple start time
    if markers[0] == 84: 
        true_session_start = np.array(rp.sessionStartTime)
        #print(true_session_start)
        session_trial_duration = rp.timeStamps[0][0] - true_session_start
        session_trial_duration = session_trial_duration * 1000  # true delay between unity start and first trial is now in milliseconds
        #print(session_trial_duration)
        finding_index = 0
        for i in range(np.shape(el.timestamps)[0]):
            if el.timestamps[i] != el.session_start[0]:
                finding_index += 1
            else:
                break
        #print(finding_index)
        el_session_trial_chunk = np.array(el.timestamps)[finding_index:int(np.array(el.trial_timestamps)[0][0])]
        el_session_trial_chunk.astype(float)
        last_point = el_session_trial_chunk[-1]
        first_point = el_session_trial_chunk[0]   
        scaled_chunk = ((el_session_trial_chunk - el_session_trial_chunk[0]) / float(last_point - first_point)) * session_trial_duration
        scaled_chunk += first_point
        shifting_needed = scaled_chunk[-1] - last_point
        start = int(np.array(el.trial_timestamps)[0][0])
        end = np.shape(el.timestamps)[0]
        el.timestamps[start:end] = el.timestamps[start:end] + shifting_needed
        el.timestamps[finding_index:start] = scaled_chunk     
        
        target = true_session_start * 1000
        full_shift = np.array(el.session_start) - target
        el.timestamps = np.uint32(el.timestamps - full_shift)
    
        
        TS = np.array(el.timestamps)
        #TS = np.transpose(TS)
        for row in range(np.shape(el.fix_times)[0]):
            el.fix_times['start'][row] = TS[int(saving_closest_fix_times[row, 0])]
            el.fix_times['end'][row] = TS[int(saving_closest_fix_times[row, 1])]
        
        
        session_trial_duration = rp.timeStamps[0][0] - true_session_start
        uf_session_trial_chunk = uf.unityTime[0][:uf.unityTriggers[0][0][0]+2]  # why + 2?
        last_point = uf_session_trial_chunk[-1]
        scaled_chunk = (uf_session_trial_chunk/last_point) * session_trial_duration
        shifting_needed = scaled_chunk[-1] - last_point
        
        uf.unityTime[0][uf.unityTriggers[0][0][0]+1:] += shifting_needed  # why + 1?
        uf.unityTime[0][:uf.unityTriggers[0][0][0]+2] = scaled_chunk
        
        uf.unityTime[0] += true_session_start  
       
    else:
        print('session start marker not recognised')
        print('unable to align timings accurately for now')        
    
        
    #%% updating unityData and unityTrialTime by inserting Nan into uf.unityTrialTime
    new_deltas = np.diff(uf.unityTime[0])
    uf.unityData[0][:,1] = new_deltas
    
    for col in range(np.shape(uf.unityTrialTime[0])[1]):    
        arr = uf.unityTime[0][uf.unityTriggers[0][col][1]-1 : uf.unityTriggers[0][col][2]]
        arr = arr - arr[0]
        a = np.empty(np.shape(uf.unityTrialTime[0])[0])
        a[:] = np.nan
        uf.unityTrialTime[0][:,col] = a;
        uf.unityTrialTime[0][:np.shape(arr)[0], col] = arr
    
    
    #%% convert back to the original unit
    el.session_start[0] = el.session_start[0]/el.samplingRate
    el.timestamps = pd.Series(el.timestamps/el.samplingRate)
    el.trial_timestamps = el.trial_timestamps/el.samplingRate
    el.fix_times = el.fix_times/el.samplingRate    
    
    #%% Saving
    #uf_n = uf.get_filename()
    #el_n = el.get_filename()
    #hkl.dump(uf,uf_n,'w')
    #hkl.dump(el,el_n,'w')
    uf.save()
    el.save()
    
    print('finish aligning objects')
            


        
        
