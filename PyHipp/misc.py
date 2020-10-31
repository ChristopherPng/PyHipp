def getChannelInArray(channel_name, fig):
    rows = 5
    cols = 8
    channel_num = int(channel_name[-3:])
    if channel_num < 7:
        spind = channel_num + 1
    elif channel_num < 33:
        spind = channel_num + 2
    elif channel_num < 65:
        spind = channel_num - 30
    elif channel_num < 97:
        spind = channel_num - 62
    elif channel_num < 119:
        spind = channel_num - 94
    else:
        spind = channel_num - 93

    # check if it is the corner subplot so we can add ticks and labels
    isCorner = 0
    if channel_num < 97:
    	if spind == 33:
    	    isCorner = 1
    else:
    	if spind == 26:
    	    isCorner = 1
    	    
    return fig.add_subplot(rows, cols, spind), isCorner
