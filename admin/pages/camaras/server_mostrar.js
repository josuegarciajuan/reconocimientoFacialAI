Stream = require('node-rtsp-stream')
stream = new Stream({
name: 'name',
streamUrl: 'rtsp://admin:bakcAse4@172.16.51.51:554/cam/realmonitor?channel=1&subtype=0',
wsPort: 9999,
ffmpegOptions: { // options ffmpeg flags
  '-stats': '', // an option with no neccessary value uses a blank string
  '-r': 30 // options with required values specify the value after the key
}
})