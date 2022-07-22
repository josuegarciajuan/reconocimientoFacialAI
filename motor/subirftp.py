import pysftp
cnopts = pysftp.CnOpts()
cnopts.hostkeys = None   
myHostname = "217.61.112.100"
myUsername = "testuser"
myPassword = "prueba123"

with pysftp.Connection(host=myHostname, username=myUsername, password=myPassword, cnopts=cnopts) as sftp:
    print ("Connection succesfully stablished ... ")
    sftp.put('output.out','tets.out')
    sftp.close()
os.remove(video_actual)