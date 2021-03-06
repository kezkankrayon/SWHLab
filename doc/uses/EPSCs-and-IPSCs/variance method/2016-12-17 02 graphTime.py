import os
import sys
sys.path.append("../../../../")
import swhlab
import matplotlib.pyplot as plt
import matplotlib.mlab as mlab
import numpy as np
import time


class ABF2(swhlab.ABF):
    def phasicTonic(self,m1=None,m2=None,chunkMs=50,quietPercentile=10,
                    histResolution=.5,plotToo=False,rmsExpected=5):
        """ 
        chunkMs should be ~50 ms or greater.
        bin sizes must be equal to or multiples of the data resolution.
        transients smaller than the expected RMS will be silenced.
        """
        # prepare sectioning values to be used later
        m1=0 if m1 is None else m1*self.pointsPerSec
        m2=len(abf.sweepY) if m2 is None else m2*self.pointsPerSec
        m1,m2=int(m1),int(m2)
        
        # prepare histogram values to be used later
        padding=200 # pA or mV of maximum expected deviation
        chunkPoints=int(chunkMs*self.pointsPerMs)
        histBins=int((padding*2)/histResolution)
        
        # center the data at 0 using peak histogram, not the mean
        Y=self.sweepY[m1:m2]
        hist,bins=np.histogram(Y,bins=2*padding)
        Yoffset=bins[np.where(hist==max(hist))[0][0]]
        Y=Y-Yoffset # we don't have to, but PDF math is easier
        
        # calculate all histogram
        nChunks=int(len(Y)/chunkPoints)
        hist,bins=np.histogram(Y,bins=histBins,range=(-padding,padding))
        hist=hist/len(Y) # count as a fraction of total
        Xs=bins[1:]

        # get baseline data from chunks with smallest variance
        chunks=np.reshape(Y[:nChunks*chunkPoints],(nChunks,chunkPoints))
        variances=np.var(chunks,axis=1)
        percentiles=np.empty(len(variances))
        for i,variance in enumerate(variances):
            percentiles[i]=sorted(variances).index(variance)/len(variances)*100
        blData=chunks[np.where(percentiles<=quietPercentile)[0]].flatten()
        
        # generate the standard curve and pull it to the histogram height
        sigma=np.sqrt(np.var(blData))
        center=np.average(blData)+histResolution/2
        blCurve=mlab.normpdf(Xs,center,sigma)
        blCurve=blCurve*max(hist)/max(blCurve)
                
        # determine the phasic current by subtracting-out the baseline
        diff=hist-blCurve
        
        # manually zero-out data which we expect to be within the RMS range
        ignrCenter=len(Xs)/2
        ignrPad=rmsExpected/histResolution
        ignr1,ignt2=int(ignrCenter-ignrPad),int(ignrCenter+ignrPad)
        diff[ignr1:ignt2]=0
            
        return diff/len(Y)*abf.pointsPerSec # charge/sec

if __name__=="__main__":
    #abfPath=r"X:\Data\2P01\2016\2016-09-01 PIR TGOT"
    abfPath=r"C:\Users\scott\Documents\important\demodata"   
    abf=ABF2(os.path.join(abfPath,"16d14036.abf"))   
    
    t=time.perf_counter()
    Xs=np.arange(abf.sweeps)*abf.sweepLength
    pos,neg=np.zeros(len(Xs)),np.zeros(len(Xs))
    for sweep in abf.setsweeps():
        phasic=abf.phasicTonic(.75)
        neg[sweep],pos[sweep]=np.sum(np.split(phasic,2),1)
    t=time.perf_counter()-t
        
    plt.figure(figsize=(10,5))
    plt.grid()
    plt.title("analysis of %s completed in %.02f S"%(abf.ID,t))
    plt.plot(Xs,pos,'.',color='b',alpha=.3)
    plt.plot(Xs,swhlab.common.lowpass(pos),'-',color='b',alpha=.5,lw=5,label="upward")
    plt.plot(Xs,neg,'.',color='r',alpha=.3)
    plt.plot(Xs,swhlab.common.lowpass(neg),'-',color='r',alpha=.5,lw=5,label="downward")
    for sweep in abf.comment_times:
        plt.axvline(sweep,lw=5,alpha=.5,color='g',ls='--')
    plt.axhline(0,color='k',lw=3,alpha=.5)
    plt.xlabel("time (secods)")
    plt.ylabel("ms * pA / sec")
    plt.legend(loc='upper left',shadow=True)
    plt.margins(0,.1)
    plt.show()
        
    
    print("DONE")