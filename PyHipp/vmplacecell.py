import DataProcessingTools as DPT
import matplotlib.pyplot as plt
from .spiketrain import Spiketrain
from .umaze import Umaze
import numpy as np 

class VMPlaceCell(DPT.DPObject):
    # Please change the class name according to your needs
    filename = 'vmplacecell.hkl'  # this is the filename that will be saved if it's run with saveLevel=1
    argsList = [('GridSteps', 40), ('OverallGridSize', 25)]  # these is where arguments used in the creation of the object are listed
    level = 'cell'  # this is the level that this object will be created in

    def __init__(self, *args, **kwargs):
        DPT.DPObject.__init__(self, *args, **kwargs)

    def create(self, *args, **kwargs):
        # this function will be called once to create this waveform object
        um = Umaze(*args, **kwargs)
        st = Spiketrain(*args, **kwargs)
        
        # Example:
        if len(um.dirs)>0 and len(st.dirs)>0:
            # create object if data is not empty
            DPT.DPObject.create(self, *args, **kwargs)

            # compute variables related to GridSteps
            gridSteps = self.args['GridSteps']
            gridSize = self.args['OverallGridSize']
            halfGridSize = gridSize / 2
            gridStepSize = gridSize / gridSteps          

            # convert from milliseconds to seconds
            stimes = np.array(st.spiketimes[0], dtype='float') / 1000

            # get Unity information
            stedges = um.sessionTime[:,0]
            umst = um.sessionTime
            
            # ignore spiketimes before the start of the Unity program
            # and after the end of the Unity program
            stimes2 = stimes[(stimes>stedges[1]) & (stimes<stedges[-1])]
            # get the corresponding bin number (row_index) for each spiketime
            bin_number = np.digitize(stimes2,stedges) - 1
            gp = umst[bin_number,1]
            gp2 = gp[gp>0] - 1
            # perform histogram
            histcounts, bins = np.histogram(gp2, bins=np.arange(gridSteps*gridSteps+1))
            self.placebins = np.reshape(histcounts,(-1,1))
            self.numSets = 1

        else:
            # create empty object if data is empty
            DPT.DPObject.create(self, dirs=[], *args, **kwargs)            
        
    def append(self, wf):
        DPT.DPObject.append(self, wf)  # append self.setidx and self.dirs
        # append histcounts
        self.placebins = np.concatenate((self.placebins, wf.placebins), axis=1)
        self.numSets = self.numSets + wf.numSets
        
    def plot(self, i = None, ax = None, getNumEvents = False, getLevels = False,\
             getPlotOpts = False, overlay = False, **kwargs):
        # this function will be called in different instances in PanGUI.main
        # Eg. initially creating the window, right-clicking on the axis and click on any item
        # input argument:   'i' is the current index in the data list to plot 
        #                   'ax' is the axis to plot the data in
        #                   'getNumEvents' is the flag to get the total number of items and the current index of the item to plot, which is 'i'
        #                   'getLevels' is the flag to get the level that the object is supposed to be created in
        #                   'getPlotOpts' is the flag to get the plotOpts for creating the menu once we right-click the axis in the figure
        #                   'kwargs' is the keyward arguments pairs to update plotOpts
        
        # plotOpts is a dictionary to store the information that will be shown 
        # in the menu evoked by right-clicking on the axis after the window is created by PanGUI.create_window
        # for more information, please check in PanGUI.main.create_menu
        plotOpts = {'PlotType': DPT.objects.ExclusiveOptions(['Channel'], 0), \
            'TitleOff': False}

        # update the plotOpts based on kwargs, these two lines are important to
        # receive the input arguments and act accordingly
        for (k, v) in plotOpts.items():
                    plotOpts[k] = kwargs.get(k, v)  
                    
        plot_type = plotOpts['PlotType'].selected()  # this variable will store the selected item in 'Type'

        if getPlotOpts:  # this will be called by PanGUI.main to obtain the plotOpts to create a menu once we right-click on the axis
            return plotOpts 

        if getNumEvents:  
            return self.numSets, i
                
        if ax is None:
            ax = plt.gca()

        if not overlay:
            ax.clear()
        
        ######################################################################
        #################### start plotting ##################################
        ######################################################################
        if plot_type == 'Channel':  # plot in channel level
            # reshape data for plotting
            gridSteps = self.args['GridSteps']
            y = np.reshape(self.placebins[:,i], (gridSteps,gridSteps), order='F')
            ax.imshow(y, origin='lower')
            # plt.colorbar(ax=ax)
    
        ########labels###############
        if not plotOpts['TitleOff']:  # if TitleOff icon in the right-click menu is clicked
            # set the title in this format: channelxxx, fill with zeros if the channel number is not three-digit
            ax.set_title(self.dirs[i])
