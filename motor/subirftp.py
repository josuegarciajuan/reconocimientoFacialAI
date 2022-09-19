import pysftp

import warnings
warnings.filterwarnings('ignore','.*Failed to load HostKeys.*')

cnopts = pysftp.CnOpts()
cnopts.hostkeys = None 



# myHostname = "217.61.112.100"
# myUsername = "testuser"
# myPassword = "prueba123"

myHostname = "45.136.70.236"
myUsername = "testuser"
myPassword = "prueba123"


with pysftp.Connection(host=myHostname, username=myUsername, password=myPassword, cnopts=cnopts) as sftp:
    print ("Connection succesfully stablished ... ")
    sftp.put("/var/www/html/reconocimientofacialV2/motor/videos/1/1_2022-09-19_11:03:54.107124.avi",'motor/videos/1/1/video.avi')
    sftp.close()
# os.remove(video_actual)



