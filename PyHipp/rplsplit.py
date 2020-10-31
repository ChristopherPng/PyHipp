import numpy as np 
import neo  
from neo.io import BlackrockIO 
import os 
import glob 
from . import rplraw 
from .rplparallel import RPLParallel
# from .mountain_batch import mountain_batch
# from .export_mountain_cells import export_mountain_cells
from . import rpllfp
from . import rplhighpass
import DataProcessingTools as DPT 


class RPLSplit(DPT.DPObject):

	filename = 'rplsplit.hkl'
	argsList = [('channel', [*range(1, 125)]), ('SkipHPC', True), ('SkipLFP', True), ('SkipHighPass', True), ('SkipSort', True), ('SkipParallel', True)] 
	level = 'session'

	def __init__(self, *args, **kwargs):
		rr = DPT.levels.resolve_level(self.level, os.getcwd())
		with DPT.misc.CWD(rr):
			DPT.DPObject.__init__(self, *args, **kwargs)

	def create(self, *args, **kwargs):

		if not self.args['SkipParallel']: 
			print('Calling RPLParallel...')
			rp = RPLParallel(saveLevel = 1)

		ns5File = glob.glob('*.ns5')
		if len(ns5File) > 1: 
			print('Too many .ns5 files, do not know which one to use.')
			# create empty object
			DPT.DPObject.create(self, dirs=[], *args, **kwargs)            
			return 
		if len(ns5File) == 0:
			print('.ns5 file missing')
			# create empty object
			DPT.DPObject.create(self, dirs=[], *args, **kwargs)            
			return 
		# create object
		DPT.DPObject.create(self, *args, **kwargs)
		reader = BlackrockIO(ns5File[0])
		bl = reader.read_block(lazy = True)
		print('.ns5 file loaded.')
		segment = bl.segments[0]
		if len(glob.glob('*.ns2')) == 0: # Check if .ns2 file is present, if its not present adjust the index for raw signals accordingly 
			index = 1 
		else:
			index = 2
		chx = bl.channel_indexes[index] # For the raw data.
		analogInfo = {} 
		analogInfo['SampleRate'] = float(segment.analogsignals[index].sampling_rate)
		annotations = chx.annotations
		names = list(map(lambda x: str(x), chx.channel_names))

		def process_channel(data, annotations, chxIndex, analogInfo, channelNumber, returnData = False):
			analogInfo['Units'] = 'uV'
			analogInfo['HighFreqCorner'] = float(annotations['nev_hi_freq_corner'][chxIndex])
			analogInfo['HighFreqOrder'] = annotations['nev_hi_freq_order'][chxIndex]
			analogInfo['HighFilterType'] = annotations['nev_hi_freq_type'][chxIndex]
			analogInfo['LowFreqCorner'] = float(annotations['nev_lo_freq_corner'][chxIndex])
			analogInfo['LowFreqOrder'] = annotations['nev_lo_freq_order'][chxIndex]
			analogInfo['LowFilterType'] = annotations['nev_lo_freq_type'][chxIndex]
			analogInfo['MaxVal'] = np.amax(data)
			analogInfo['MinVal'] = np.amin(data)
			analogInfo['NumberSamples'] = len(data)
			analogInfo['ProbeInfo'] = names[chxIndex]
			if returnData:
				return analogInfo
			arrayNumber = annotations['connector_ID'][chxIndex] + 1
			arrayDir = "array{:02d}".format(int(arrayNumber))
			channelDir = "channel{:03d}".format(int(channelNumber))
			directory = os.getcwd() # Go to the channel directory and save file there. 
			if arrayDir not in os.listdir('.'): 
				os.mkdir(arrayDir)
			os.chdir(arrayDir)
			if channelDir not in os.listdir('.'):
				os.mkdir(channelDir)
			os.chdir(channelDir)
			print('Calling RPLRaw for channel {:03d}'.format(channelNumber))
			rplraw.RPLRaw(analogData = data, analogInfo = analogInfo, saveLevel = 1)
			if self.args['SkipHPC']:
				if not self.args['SkipLFP']:
					print('Calling RPLLFP for channel {:03d}'.format(channelNumber))
					rpllfp.RPLLFP(saveLevel = 1)
				if not self.args['SkipHighPass']:
					print('Calling RPLHighPass for channel {:03d}'.format(channelNumber))
					rplhighpass.RPLHighPass(saveLevel = 1)
				if DPT.levels.get_level_name('session', os.getcwd()) != 'sessioneye':
					if not self.args['SkipSort']:
						print('Calling Mountain Sort for channel {:03d}'.format(channelNumber))
						# mountain_batch()
						# export_mountain_cells()
			else: 
				if 'HPCScriptsDir' not in kwargs.keys():
					kwargs['HPCScriptsDir'] = ''
				print('Adding RPLLFP slurm script for channel {:03d} to job queue'.format(channelNumber))
				os.system('sbatch ' + kwargs['HPCScriptsDir'] + 'rpllfp-slurm.sh')
				if not self.args['SkipSort']:
					print('Adding RPLHighPass and Mountain Sort slurm script for channel {:03d} to job queue'.format(channelNumber))
					os.system('sbatch '+ kwargs['HPCScriptsDir'] + 'rplhighpass-sort-slurm.sh')
				else:
					print('Adding RPLHighPass slurm script for channel {:03d} to job queue'.format(channelNumber))
					os.system('sbatch ' + kwargs['HPCScriptsDir'] + 'rplhighpass-slurm.sh')
			os.chdir(directory)
			print('Channel {:03d} processed'.format(channelNumber))
			return 

		if 'returnData' in kwargs.keys(): 
			i = self.args['channel'][0]
			chxIndex = names.index(list(filter(lambda x: str(i) in x, names))[0])
			data = np.array(segment.analogsignals[index].load(time_slice=None, channel_indexes=[chx.index[chxIndex]]))
			analogInfo = process_channel(data, annotations, chxIndex, analogInfo, i, returnData = True)
			print('Returning data and analogInfo to RPLRaw')
			self.data = data 
			self.analogInfo = analogInfo 
			return 

		channelNumbers = []
		channelIndexes = []
		for i in self.args['channel']:
			chxIndex = list(filter(lambda x: int(i) == int(x[6:len(x) - 1]),names))
			if len(chxIndex) > 0:
				chxIndex = names.index(chxIndex[0])
				channelNumbers.append(i)
				channelIndexes.append(chxIndex)

		if kwargs.get('byChannel',0):
			for ind, idx in enumerate(channelIndexes):
				data = np.array(segment.analogsignals[index].load(time_slice = None, channel_indexes = [idx]))
				print('Processing channel {:03d}'.format(channelNumbers[ind]))
				process_channel(data, annotations, idx, analogInfo, channelNumbers[ind])
				del data # to create RAM space to load in the next channel data.
			return 

		else: 
			if len(channelIndexes) > 0:
				numOfIterations = int(np.ceil(len(channelIndexes) / 32))
				for k in range(numOfIterations):
					tempIndexes = channelIndexes[k*32:(k + 1) * 32]
					tempNumbers = channelNumbers[k*32:(k + 1) * 32]
					data = np.array(segment.analogsignals[index].load(time_slice=None, channel_indexes=tempIndexes))
					for ind, idx in enumerate(tempIndexes):
						print('Processing channel {:03d}'.format(tempNumbers[ind]))
						process_channel(np.array(data[:, ind]), annotations, idx, analogInfo, tempNumbers[ind])
					del data # to create RAM space to load in the next set of channel data. 
			return 
