"""
methods related to detection/reporting of action potentials.
Good for deterining AP frequency and making gain functions.

Currently AP detection is locked into derivative threshold detection.
A new detection method warrants a new module. 
The same class method names could be used though.

Detection is optimized for sweeps, not really continuous recordings.
There's a potential that an AP may be lost within a few ms from an edge.
"""

import logging
import common
from abf import ABF
import numpy as np

# REMOVE THIS:
import matplotlib.pyplot as plt

ms=.001 # easy access to a millisecond

class AP:
    def __init__(self,abf,loglevel=logging.DEBUG):
        """
        Load an ABF and get ready to do AP detection.
        After detect(), all AP data is stored as a list of dicts in AP.APs
        """
        self.log = logging.getLogger("swhlab AP")
        self.log.setLevel(loglevel)
        
        # prepare ABF class
        if type(abf) is str:
            self.log.debug("filename given, turning it into an ABF class")
            abf=ABF(abf)
        self.abf=abf
        
        # detection settings
        self.detect_over = 50 # must be at least this (mV/ms)
        
        # data storage
        self.APs=False # becomes [] when detect() is run
        
    def info(self):
        print("%d APs in memory."%len(self.APs))

    ### DETECTION
        
    def ensureDetection(self):
        """
        run this before analysis. Checks if event detection occured.
        If not, runs AP detection on all sweeps.
        """
        if self.APs==False:
            self.log.debug("analysis attempted before event detection...")
            self.detect()
    
    def detect(self):
        """runs AP detection on every sweep."""
        self.log.info("initializing AP detection on all sweeps...")
        t1=common.timeit()
        for sweep in range(self.abf.sweeps):
            self.detectSweep(sweep)
        self.log.info("AP analysis of %d sweeps found %d APs (completed in %s)",
                      self.abf.sweeps,len(self.APs),common.timeit(t1))
        
    def detectSweep(self,sweep=0):
        """perform AP detection on current sweep."""
        
        if self.APs is False: # indicates detection never happened
            self.APs=[] # now indicates detection occured
        
        # delete every AP from this sweep from the existing array
        for i,ap in enumerate(self.APs):
            if ap["sweep"]==sweep:
                self.APs[i]=None
        if self.APs.count(None):
            self.log.debug("deleting %d existing APs from memory",self.APs.count(None))
            while None in self.APs:
                self.APs.remove(None)
        self.log.debug("initiating AP detection (%d already in memory)",len(self.APs))
        
        self.abf.derivative=True
        self.abf.setsweep(sweep)

        # detect potential AP (Is) by a dV/dT threshold crossing        
        Is = common.where_cross(self.abf.sweepD,self.detect_over) 
        self.log.debug("initial AP detection: %d APs"%len(Is))
                
        # eliminate APs where dV/dT doesn't cross below -10 V/S within 2 ms
        for i,I in enumerate(Is):
            if np.min(self.abf.sweepD[I:I+2*self.abf.pointsPerMs])>-10:
                Is[i]=0
        Is=Is[np.nonzero(Is)]
        self.log.debug("after lower threshold checking: %d APs"%len(Is))

        # walk 1ms backwards and find point of +10 V/S threshold crossing
        for i,I in enumerate(Is):
            try:
                chunk=-self.abf.sweepD[I-1*self.abf.pointsPerMs:I][::-1]
                stepsBack=common.where_cross(chunk,-10)[0] # walking backwards
                Is[i]-=stepsBack # this is really splitting hairs
            except:
                self.log.debug("not stepping back AP %d/%d of sweep %d",i,len(Is),sweep)

        # analyze each AP
        sweepAPs=[]
        for i,I in enumerate(Is):
            ap={} # create the AP entry
            ap["sweep"]=sweep # number of the sweep containing this AP
            ap["I"]=I # index sweep point of start of AP (10 mV/ms threshold crossing)
            ap["Tsweep"]=I/self.abf.pointsPerSec # time in the sweep of index crossing (sec)
            ap["T"]=ap["Tsweep"]+self.abf.sweepInterval*sweep # time in the experiment
            ap["Vthreshold"]=self.abf.sweepY[I] # threshold at rate of -10mV/ms
            
            # determine how many points from the start dV/dt goes below -10 (from a 5ms chunk)
            chunk=self.abf.sweepD[I:I+5*self.abf.pointsPerMs] # give it 5ms to cross once
            I_toNegTen=np.where(chunk<-10)[0][0]
            chunk=self.abf.sweepD[I+I_toNegTen:I+I_toNegTen+10*self.abf.pointsPerMs] # give it 10ms to cross back
            I_recover=np.where(chunk>-10)[0][0]+I_toNegTen+I # point where trace returns to above -10 V/S
            ap["dVfastIs"]=[I,I_recover] # span of the fast component of the dV/dt trace
            ap["dVfastMS"]=(I_recover-I)/self.abf.pointsPerMs # time (in ms) of this fast AP component

            # determine derivative min/max from a 2ms chunk
            chunk=self.abf.sweepD[ap["dVfastIs"][0]:ap["dVfastIs"][1]]
            ap["dVmax"]=np.max(chunk)
            ap["dVmaxI"]=np.where(chunk==ap["dVmax"])[0][0]+I
            ap["dVmin"]=np.min(chunk)
            ap["dVminI"]=np.where(chunk==ap["dVmin"])[0][0]+I

            # before determining AP shape stats, see where trace recovers to threshold
            chunkSize=self.abf.pointsPerMs*10 #AP shape may be 10ms
            if len(Is)-1>i and Is[i+1]<(I+chunkSize): # if slow AP runs into next AP
                chunkSize=Is[i+1]-I # chop it down
            ap["VslowIs"]=[I,I+chunkSize] # time range of slow AP dynamics
            chunk=self.abf.sweepY[I:I+chunkSize]
            
            # determine AP peak and minimum
            ap["Vmax"]=np.max(chunk)
            ap["VmaxI"]=np.where(chunk==ap["Vmax"])[0][0]+I
            ap["Vmin"]=np.min(chunk)
            ap["VminI"]=np.where(chunk==ap["Vmin"])[0][0]+I
            if ap["VminI"]<ap["VmaxI"]:
                self.log.error("how is the AHP before the peak?")
            ap["msRiseTime"]=(ap["VmaxI"]-I)/self.abf.pointsPerMs # time from threshold to peak
            ap["msFallTime"]=(ap["VminI"]-ap["VmaxI"])/self.abf.pointsPerMs # time from peak to nadir
            
            # determine halfwidth
            ap["Vhalf"]=np.average([ap["Vmax"],ap["Vthreshold"]]) # half way from threshold to peak
            ap["VhalfI1"]=common.where_cross(chunk,ap["Vhalf"])[0]+I # time it's first crossed
            ap["VhalfI2"]=common.where_cross(-chunk,-ap["Vhalf"])[1]+I # time it's second crossed
            ap["msHalfwidth"]=(ap["VhalfI2"]-ap["VhalfI1"])/self.abf.pointsPerMs # time between crossings
            
            # instaneous frequency
            if len(Is)<2 or i==0:
                ap["freq"]=np.nan # conditions don't allow calculation
            else:
                ap["freq"]=self.abf.pointsPerSec/(I-Is[i-1]) # in Hz

            # AP error checking goes here
            # TODO:
            
            # if we got this far, add the AP to the list
            sweepAPs.extend([ap])
            
        self.log.debug("finished analyzing sweep. Found %d APs",len(sweepAPs))
        self.APs.extend(sweepAPs)
        
    ### ANALYSIS       

    def get_AP_times(self):
        """return an array of times (in sec) of all APs."""
        self.ensureDetection()
        times=[]
        for ap in self.APs:
            times.append(ap["T"])
        return np.array(sorted(times))
    
    def get_AP_times_bySweep(self):
        """return an array of times (in sec) of all APs arranged by sweep"""
        self.ensureDetection()
        timesBySweep=[[]]*self.abf.sweeps
        for sweep in range(self.abf.sweeps):
            times=[]
            for ap in self.APs:
                if ap["sweep"]==sweep:
                    times.append(ap["Tsweep"])
            timesBySweep[sweep]=np.array(sorted(times))
        return timesBySweep
        
    def get_count_bySweep(self):
        """return the number of APs in each sweep"""
        self.ensureDetection()
        sweepCounts=np.zeros(self.abf.sweeps)
        for sweep in range(self.abf.sweeps):
            for ap in self.APs:
                if ap["sweep"]==sweep:
                    sweepCounts[sweep]=sweepCounts[sweep]+1
        return sweepCounts
    
    def get_freqs_bySweep(self):
        """return the sweep by sweep list of instantaneous frequencies"""
        self.ensureDetection()
        sweepFreqs=[]
        for sweep in range(self.abf.sweeps):
            freqs=[]
            for ap in self.APs:
                if ap["sweep"]==sweep:
                    freqs.append(ap["freq"])
            sweepFreqs.append(freqs)
        return sweepFreqs
    
    def get_freq_bySweep_average(self):
        """return the sweep by sweep average of AP frequency"""
        self.ensureDetection()
        data=np.empty(self.abf.sweeps)*np.nan
        for sweep,freqs in enumerate(self.get_freqs_bySweep()):
            data[sweep]=np.nanmean(freqs)
        return np.array(data)
        
    def get_freq_bySweep_median(self):
        """return the sweep by sweep median of AP frequency"""
        self.ensureDetection()
        data=np.empty(self.abf.sweeps)*np.nan
        for sweep,freqs in enumerate(self.get_freqs_bySweep()):
            data[sweep]=np.nanmedian(freqs)
        return np.array(data)
        
if __name__=="__main__":
    abfFile=r"C:\Users\scott\Documents\important\2016-07-01 newprotos\16701009.abf"
    ap=AP(abfFile)
    print(ap.get_AP_times_bySweep())
    
    print("DONE")