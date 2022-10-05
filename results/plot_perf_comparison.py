import os
import matplotlib.pyplot as plt
import pandas as pd

currDir = os.path.dirname(os.path.realpath(__file__))
Nebula_LOG_PATH = os.path.join(currDir, 'wifi.perf.1/ifbw.cl.log')
WebRTC_LOG_PATH = os.path.join(currDir, 'wifi.perf.1/ifbw.rtc.cl.log')

fig, axes = plt.subplots(3,1, figsize=(10,6))

#Bandwidth Utility
nebulaThourghputDF = pd.read_csv(Nebula_LOG_PATH)
webrtcThourghputDF = pd.read_csv(WebRTC_LOG_PATH)
webrtcThourghputDF = webrtcThourghputDF.groupby(['seconds'])['bw'].mean().reset_index()
print(webrtcThourghputDF.head())
axes[0].plot(nebulaThourghputDF['bw']/1024, label='Nebula')
axes[0].plot(webrtcThourghputDF['bw']/1024, color='red', label='WebRTC')

axes[0].spines['right'].set_visible(False)
axes[0].spines['top'].set_visible(False)
axes[0].legend()
axes[0].set_ylabel('Bandwidth utility (Mb/s)')

currDir = os.path.dirname(os.path.realpath(__file__))
Nebula_LOG_PATH = os.path.join(currDir, 'wifi.perf.1/mtp.nebula.log')
WebRTC_LOG_PATH = os.path.join(currDir, 'wifi.perf.1/mtp.rtc.log')

#Motion to photon Latency
nebulaMTPDF = pd.read_csv(Nebula_LOG_PATH)
webrtcMTPDF = pd.read_csv(WebRTC_LOG_PATH)
axes[1].plot(nebulaMTPDF['mtp'], label='Nebula')
axes[1].plot(webrtcMTPDF['mtp'], color='red', label='WebRTC')
plt.ylabel('Eduroam throughput (Mbps)')

axes[1].spines['right'].set_visible(False)
axes[1].spines['top'].set_visible(False)
axes[1].legend()
axes[1].set_ylabel('Motion-to-Photon (ms)')


#PSNR
axes[2].plot(nebulaMTPDF['psnr'], label='Nebula')
axes[2].plot(webrtcMTPDF['psnr'], color='red', label='WebRTC')
axes[2].spines['right'].set_visible(False)
axes[2].spines['top'].set_visible(False)
axes[2].set_ylabel('PSNR (dB)')
axes[2].legend()


plt.show()
