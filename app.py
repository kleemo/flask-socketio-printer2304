from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from flaskwebgui import FlaskUI # import FlaskUI

import time
import getopt
import random

from werkzeug.datastructures import ContentSecurityPolicy

from options import *
from printhandler import DefaultUSBHandler

import shapehandler
import slicerhandler

port = '/dev/tty.usbmodem14101'
baud = 250000

# connect to printer
print_handler = DefaultUSBHandler(port, baud)
slicer_handler = slicerhandler.Slicerhandler()
shape_handler = shapehandler.Shapehandler()

layer = 0
height = 0
tooplpath_type = "NONE"
printing = False

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

@app.route("/")
def index():
    return render_template('index.html')

@socketio.on('hello')
def hello():
    emit('layer', { 'layer': layer })
    emit('slicer_options', {
        'extrusion_rate': slicer_handler.params['extrusion_rate'],
        'feed_rate': slicer_handler.params['feed_rate'],
        'layer_hight': slicer_handler.params['layer_hight']
    })
    emit('toolpath_type', { 'toolpath_type': tooplpath_type })
    emit('toolpath_options', {
        'magnitude': shape_handler.params_toolpath['magnitude'],
        'wave_lenght': shape_handler.params_toolpath['wave_lenght'],
        'rasterisation': shape_handler.params_toolpath['rasterisation']
    })

@socketio.on('slicer_options')
def slicer_options(data):
    slicer_handler.params['extrusion_rate'] = data["extrusion_rate"]
    slicer_handler.params['feed_rate'] = data["feed_rate"]
    slicer_handler.params['layer_hight'] = data["layer_hight"]

@socketio.on('toolpath_options')
def toolpath_options(data):
    shape_handler.params_toolpath['magnitude'] = data["magnitude"]
    shape_handler.params_toolpath['wave_lenght'] = data["wave_lenght"]
    shape_handler.params_toolpath['rasterisation'] = data["rasterisation"]

@socketio.on('layer')
def setLayer(data):
    global layer
    layer = int(data["layer"])

@socketio.on('toolpath_type')
def setToolpath(data):
    global tooplpath_type
    tooplpath_type = data["toolpath_type"]
    print(str(tooplpath_type))

@socketio.on('printer_connect')
def printer_connect():
    print("connect")
    if print_handler.connect():
        emit('connected', {'connected': True})

@socketio.on('printer_disconnect')
def printer_disconnect():
    print_handler.disconnect()
    emit('connected', {'connected': False})

@socketio.event
def layer_to_zero():
    global layer
    layer = 0
    emit('layer', {'layer': layer})

#reset printer postition and settings
@socketio.on('printer_setup')
def printer_setup():
    print_handler.send(["G90", "M104 S210", "G28", "G91", "G1 Z10", "G90"])
    #print_handler.send(["G90", "G28"])
    while print_handler.is_printing():
        time.sleep(0.1)

@socketio.on('move_up')
def printer_up():
    print_handler.send(["G91", "G1 Z10", "G90"])
    while print_handler.is_printing():
        time.sleep(0.1)

@socketio.on('move_down')
def printer_down():
    print_handler.send(["G91", "G1 Z-10", "G90"])
    while print_handler.is_printing():
        time.sleep(0.1)

@socketio.on('printer_pause_resume')
def printer_pause_resume():
    if print_handler.is_printing():
        print_handler.pause()
    elif print_handler.is_paused():
        print_handler.resume()

def printer_extrude():
    print_handler.send(["G92 E0", "G1 E2 F100"])
    while print_handler.is_printing():
        time.sleep(0.1)

def zero_layer():
    global layer
    layer = 0
    print("layer set to O")

@socketio.on('start_print')
def start_print():
    global printing
    if(printing):
        printing = False
        return
    
    printing = True

    print_handler.send(slicer_handler.start())
    while print_handler.is_printing():
        time.sleep(0.1)

    global layer
    global height
    global tooplpath_type
    angle = 0
    # next_iteration = layer + 10
    # while layer < next_iteration:
    while printing:
        #gcode = slicerhandler.create(i, shapehandler.create_test(0.5 * i))

        wobbler = 0
        angle = angle + random.randint(-wobbler, wobbler)
        print("angle = " + str(angle))

        # create the shape points
        points = shape_handler.create_stepover(angle, 3)
        points = shape_handler.toolpath(points, tooplpath_type)

        repetitions = 1
        for i in range(repetitions):
            # create gcode from points
            gcode = slicer_handler.create(height, points)
            print_handler.send(gcode)
            while (print_handler.is_printing() or print_handler.is_paused()):
                time.sleep(0.1)
                #print(print_handler.status())
            # update layer hight
            layer = layer + 1
            height = height + slicer_handler.params['layer_hight']
            print (height)
            emit('layer', {'layer': layer})
        
    print_handler.send(slicer_handler.end())

if __name__ == '__main__':
    # socketio.run(app) for development
    FlaskUI(app, socketio=socketio, start_server="flask-socketio").run()