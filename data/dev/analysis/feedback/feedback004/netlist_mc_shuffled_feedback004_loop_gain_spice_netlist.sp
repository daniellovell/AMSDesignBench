.subckt opamp in_n in_p out
	* opamp implementation
.ends opamp
XU2 N001 0 S_out opamp Aol=100K GBW=10Meg
R436213929 S_out N001 R
R319667826 N001 S_in R
.backanno
.end

