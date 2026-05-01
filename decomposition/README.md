the decomposition/*.txt files layout the components under the respective title of the file
the /power /control /mechanical folders contain *.txt files further defining the components outlined in the decomposition/*.txt files
within the files there are flags:
	**LINK SPEC**
	**motor_spec**
	**needs_torque_verified**
	*^ [long note defining task or some element of operation] ^*

using bash commands: cat, grep, sed one should be able to find/add things surrounded by the ** ** and *^ ^* markers.
