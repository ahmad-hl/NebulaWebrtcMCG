import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
# import seaborn as sns
vp8_encode_delay =  20.8

#Motion to Photon
def computeMTP_nebula(dir_names):

    mtpDF = pd.DataFrame()
    for dir_name in dir_names:
        #Nebula Motion to Photon Calculation
        mtpDF = pd.read_csv(dir_name+'/mtp.sr.log', sep=',')
        mtpDF['mtp'] = mtpDF['mtp'] * 1000
        mtpDF.to_csv(dir_name + '/mtp.nebula.log', index=False)
        print(mtpDF.head())

    return mtpDF

def computeMTP_webRTC(dir_names):
    # WebRTC Client Display Delay
    mtpDF = pd.DataFrame()
    for dir_name in dir_names:
        display_rtcDF = pd.read_csv(dir_name+'/display.rtc.log', sep=',')
        display_rtcDF.drop(['timebase', 'pts'], axis=1, inplace=True)
        # WebRTC Server Rendering Delay
        render_rtcDF = pd.read_csv(dir_name+'/render.rtc.sr.log', sep=',')
        render_rtcDF.drop(['timebase', 'pts'], axis=1, inplace=True)

        merged_rtcDF = pd.merge(render_rtcDF, display_rtcDF, on='frame_no')
        merged_rtcDF.columns = ['frame_no', 'rendrdelay', 'rendrts', 'dispdelay', 'dispts']
        merged_rtcDF['mtp'] = merged_rtcDF.apply(lambda x: x.dispts - x.rendrts, axis=1)
        mtpDF = pd.concat([mtpDF, merged_rtcDF], ignore_index=True)
        #save to csv file
        psnr_rtcDF = pd.read_csv(dir_name + '/webrtc_psnr.log', sep='\t')
        print(psnr_rtcDF.head())
        psnr_rtcDF.columns=['frame_no','psnr']
        mtp_to_saveDF = pd.merge(mtpDF,psnr_rtcDF, on='frame_no')
        mtp_to_saveDF = mtp_to_saveDF.drop(['rendrdelay', 'rendrts','dispdelay','dispts'], axis=1)
        mtp_to_saveDF.to_csv(dir_name + '/mtp.rtc.log', index=False)

    return mtpDF


#Round Trip Time
def computeRTT_nebula(dir_names):
    #Nebula RTT
    column_names = ['seconds','ts','rtt']
    rttDF = pd.DataFrame(columns=column_names)
    for dir_name in dir_names:
        # Nebula Motion to Photon Calculation
        nebulaRTTDF = pd.read_csv(dir_name + '/rtt.sr.log', sep=',')
        rttDF = pd.concat([rttDF, nebulaRTTDF], ignore_index=True)

    return rttDF

def computeRTT_rtc(dir_names):
    # WebRTC RTT
    column_names = ['seconds','delay','client_ping_ts','server_pong_ts','client_pang_ts']
    rttDF = pd.DataFrame(columns=column_names)
    for dir_name in dir_names:
        # Nebula Motion to Photon Calculation
        rtcRTTDF = pd.read_csv(dir_name + '/rtt.rtc.sr.log', sep=',')
        rtcRTTDF = rtcRTTDF.loc[rtcRTTDF.delay < 1000]  # remove delays beyond RTT timer
        rttDF = pd.concat([rttDF, rtcRTTDF], ignore_index=True)

    return rttDF


#Experiments directories
experiments_dir_names = ['wifi.perf.1']

#Round Trip Time statsitics
nebulaRTTDF = computeRTT_nebula(experiments_dir_names)
stats_rtt_nebula = nebulaRTTDF['rtt'].agg(['mean', 'count', 'std'])
m, c, s = stats_rtt_nebula.values
stats_rtt_nebula['ci95'] = 1.96*s/math.sqrt(c)

rtcRTTDF = computeRTT_rtc(experiments_dir_names)
stats_rtt_webrtc = nebulaRTTDF['rtt'].agg(['mean', 'count', 'std'])
m, c, s = stats_rtt_webrtc.values
stats_rtt_webrtc['ci95'] = 1.96*s/math.sqrt(c)

#Motion to Photon statsitics
nebulaMTPDF = computeMTP_nebula(experiments_dir_names)
stats_mtp_nebula = nebulaMTPDF['mtp'].agg(['mean', 'count', 'std'])
m, c, s = stats_mtp_nebula.values
stats_mtp_nebula['ci95'] = 1.96*s/math.sqrt(c)

rtcMTPDF = computeMTP_webRTC(experiments_dir_names)
stats_mtp_webrtc = rtcMTPDF['mtp'].agg(['mean', 'count', 'std'])
m, c, s = stats_mtp_webrtc.values
stats_mtp_webrtc['ci95'] = 1.96*s/math.sqrt(c)

rttMeans = (stats_rtt_nebula['mean'],stats_rtt_webrtc['mean'])
rttCIs = (stats_rtt_nebula['ci95'],stats_rtt_webrtc['ci95'])
mtpMeans = (stats_mtp_nebula['mean'],stats_mtp_webrtc['mean'])
mtpCIs = (stats_mtp_nebula['ci95'],stats_mtp_webrtc['ci95'])

# Plot figure
ind = ['Nebula', 'WebRTC']
width = 0.4  # the width of the bars: can also be len(x) sequence

# fig, (ax1, ax2) = plt.subplots(2, sharex=True)
fig = plt.figure(figsize=(16, 8))
ax = fig.add_subplot(111)
# color='skyblue': indianred, dodgerblue, turquoise, mediumseagreen, lightgreen
p1 = ax.bar(ind, mtpMeans, width, yerr=mtpCIs, log=False, capsize=3,
             color='dodgerblue', error_kw=dict(elinewidth=2, ecolor='black'))
# p2 = ax.bar(ind, rttMeans, width, yerr=rttCIs, log=False, capsize=3,
#              color='indianred',error_kw=dict(elinewidth=2, ecolor='brown'))

plt.margins(0.01, 0)

# Optional code - Make plot look nicer
i = 0.15
for row in mtpMeans:
    plt.text(i, row, "{0:.1f}".format(row), color='black', ha="center", fontsize=18)
    i = i + 1

# i=0.15
# totop = 60
# for rlnc,vpx in zip (rlncMeans,vpxMeans):
#     plt.text(i,rlnc + vpx, "{0:.1f}".format(rlnc+vpx), color='black', ha="center", fontsize=22)
#     i = i + 1

ax.spines['right'].set_visible(False)
ax.spines['top'].set_visible(False)
plt.tick_params(axis="y", labelsize=20, labelcolor="black")
plt.tick_params(axis="x", labelsize=20, labelcolor="black")
plt.title('Eduroam WiFi', fontsize=20)
plt.ylabel('Motion to Photon (ms)', fontsize=20)

# plt.savefig('mtp_rtt_wifi.png', bbox_inches='tight')
# fig.savefig('mtp_rtt_wifi.eps', format='eps',bbox_inches='tight')
plt.show()