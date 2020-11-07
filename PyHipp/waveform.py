import DataProcessingTools as DPT
import matplotlib.pyplot as plt
import hickle as hkl
import os
import numpy as np
from .misc import getChannelInArray


class Waveform(DPT.DPObject):
    # Please change the class name according to your needs
    filename = 'waveform.hkl'  # this is the filename that will be saved if it's run with saveLevel=1
    argsList = []  # these is where arguments used in the creation of the object are listed
    level = 'channel'  # this is the level that this object will be created in

    def __init__(self, *args, **kwargs):
        DPT.DPObject.__init__(self, *args, **kwargs)

    def create(self, *args, **kwargs):

        # this function will be called once to create this waveform object
        
        # one neat property of Object-Oriented Programming (OOP) structure is that 
        # you can create some field-value pairs that can be called and updated 
        # in all functions of the object, if you specify the function properly.
        # The only thing that you need to do is to instantiate those fields in
        # this function with the prefix 'self.', then you can call them and 
        # edit them in all the other functions that have the first input argument
        # being 'self'
        #
        # For exmample, if you instantiate a field-value pair:
        # self.name = IronMan
        #
        # You can then call them or edit them in other functions:
        # def get_name(self):
        #    print(self.name)
        #
        # def set_name(self, new_name):
        #    self.name = new_name
        #
        # In this way, you don't need to return and pass in so many arguments 
        # across different functions anymore :)
        
        
        # The following is some hints of the things-to-do:
        
        # read the mountainsort template files
        pwd = os.path.normpath(os.getcwd());
        
        # 'channelxxx, xxx is the number of the channel'
        self.channel_filename = [os.path.basename(pwd)]  
        template_filename = os.path.join(
                DPT.levels.resolve_level('day', self.channel_filename[0]),
                'mountains', self.channel_filename[0], 'output', 'templates.hkl')
        
        templates = hkl.load(template_filename)
        self.data = [np.squeeze(templates)]
        
        aname = DPT.levels.normpath(os.path.dirname(pwd))
        
        self.array_dict = dict()
        self.array_dict[aname] = 0
        
        self.numSets = 1
        self.current_plot_type = None

        # check on the mountainsort template data and create a DPT object accordingly
        # Example:
        if self.data:
            # create object if data is not empty
            DPT.DPObject.create(self, *args, **kwargs)
        else:
            # create empty object if data is empty
            DPT.DPObject.create(self, dirs=[], *args, **kwargs)            
        
    def append(self, wf):
        # this function will be called by processDirs to append the values of certain fields
        # from an extra object (wf) to this object
        # It is useful to store the information of the objects for panning through in the future
        DPT.DPObject.append(self, wf)  # append self.setidx and self.dirs
        self.data = self.data + wf.data
        for ar in wf.array_dict:
            self.array_dict[ar] = self.numSets
        self.numSets += 1    
        
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
        plotOpts = {'PlotType': DPT.objects.ExclusiveOptions(['Channel', 'Array'], 0), \
            'LabelsOff': False, 'TitleOff': False, 'TicksOff': False}

        # update the plotOpts based on kwargs, these two lines are important to
        # receive the input arguments and act accordingly
        for (k, v) in plotOpts.items():
            plotOpts[k] = kwargs.get(k, v)  
                    
        plot_type = plotOpts['PlotType'].selected()  # this variable will store the selected item in 'Type'

        if getPlotOpts:  # this will be called by PanGUI.main to obtain the plotOpts to create a menu once we right-click on the axis
            return plotOpts 
        
        if self.current_plot_type is None:
            self.current_plot_type = plot_type

        if getNumEvents:  
            # this will be called by PanGUI.main to return two values: 
            # first value is the total number of items to pan through, 
            # second value is the current index of the item to plot
            if self.current_plot_type == plot_type:
                if plot_type == 'Channel':
                    return self.numSets, i
                elif plot_type == 'Array':
                    return len(self.array_dict), i
            elif self.current_plot_type == 'Array' and plot_type == 'Channel':
                # add code to return number of channels and the appropriate
                # channel number if the current array number is i
                return self.numSets, i * (self.numSets // len(self.array_dict))
            elif self.current_plot_type == 'Channel' and plot_type == 'Array':  
                # add code to return number of arrays and the appropriate
                # array number if the current channel number is i
                self.current_plot_type = 'Array'
                return len(self.array_dict), i//self.numSets

        if ax is None:
            ax = plt.gca()

        if not overlay:
            ax.clear()
        
        ######################################################################
        #################### start plotting ##################################
        ######################################################################
        fig = ax.figure  # get the parent figure of the ax
        
        if plot_type == 'Channel':  # plot in channel level
            if self.current_plot_type == 'Array':
                self.remove_subplots(fig)
                ax = fig.add_subplot(1,1,1)    
            self.plot_data(i, ax, plotOpts, True)
        elif plot_type == 'Array':
            self.remove_subplots(fig)
            advals = np.array([*self.array_dict.values()])
            # set the starting index cstart for array i
            if i == 0:
                cstart = 0
            else:
                cstart = advals[i-1] + 1
                
            # set the ending index cend for array i
            cend = advals[i]
            currch = cstart
            while currch <= cend :
                # get channel name
                currchname = self.dirs[currch]
                plotOpts['LabelsOff'] = True
                # get axis position for channel
                ax, isCorner = getChannelInArray(currchname, fig)
                self.plot_data(currch, ax, plotOpts, isCorner)
                currch += 1

        return ax
    
    def plot_data(self, i, ax, plotOpts, isCorner):
        y = self.data[i]
        x = np.arange(y.shape[0])
        ax.plot(x, y)
    
        ########labels###############
        if not plotOpts['TitleOff']:  # if TitleOff icon in the right-click menu is clicked
            # set the title in this format: channelxxx, fill with zeros if the channel number is not three-digit
            ax.set_title(self.dirs[i])
            
        if (not plotOpts['LabelsOff']) or isCorner:  # if LabelsOff icon in the right-click menu is clicked
            # set the xlabel and ylabel
            ax.set_xlabel('Time (sample unit)')
            ax.set_ylabel('Voltage (uV)')
            
        if plotOpts['TicksOff'] or (not isCorner):
            ax.set_xticklabels([])
            ax.set_yticklabels([])
            
    def remove_subplots(self, fig):
        for x in fig.get_axes():  # remove all axes in current figure
            x.remove()

    
    #%% helper functions        
    # Please make use of the properties of the OOP to call and edit the field-value
    # pairs that can be shared across different functions in this object.
    # This will greatly increase the efficiency in maintaining the codes,
    # especially for those lines that are used for multiple times in multiple places.
    # Other than that, this will also greatly increase the readability of the code
        
        