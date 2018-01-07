#-*- coding:utf-8 -*-

import time
import subprocess
import re
import logging
import sys
import RPi.GPIO as GPIO
import signal
import threading

#set the logger
logger = logging.Logger('logger1',level=logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s-%(filename)s-%(lineno)s-%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

#init
exist = False
exist_old = False
time_on = 0
stop_event = threading.Event()
lock = threading.Lock()
TIME_UP = 3600

def client_exists():
    linecount = subprocess.check_output('echo "$(create_ap --list-clients wlan0)" | wc -l',shell=True)
    linecount = int(linecount)
    return True if linecount > 1 else False 


def connect():
    #modify the default route
    p_default = re.compile('default')
    ret_route = subprocess.check_output('ip route',shell=True)
    for i in range(len(p_default.findall(ret_route))):
        subprocess.check_output('ip route del default',shell=True)
    logger.debug('ip route is \n%s\n'%subprocess.check_output('ip route',shell=True))#print the current route
    
    #connect the ppp0
    subprocess.check_output('/usr/bin/pon dsl-provider',shell=True)
    time.sleep(9)

    p_ppp0 = re.compile('ppp0')
    ret_ifconfig = subprocess.check_output('ifconfig',shell=True)
    logger.debug('9s after connection \n%s\n'%ret_ifconfig)

    while len(p_ppp0.findall(ret_ifconfig)) < 1:
        logger.info('connection tempararily fails')
        ret_ifconfig = subprocess.check_output('ifconfig',shell=True)
        time.sleep(9)    
        logger.debug('waiting ifconfig \n %s \n'%ret_ifconfig)

    
    logger.info('ppp0 appears, trying to add default route for ppp0')
    logger.debug('current ip route \n %s \n'%subprocess.check_output('ip route',shell=True))
    
    try:
        ret_route = subprocess.check_output('ip route',shell=True)
        if len(p_default.findall(ret_route)) == 0:
            subprocess.check_output('ip route add default dev ppp0',shell=True)

    except BaseException,e:
        print 'error appears'
    logger.info('default route added')


def disconnect():
    try:
        subprocess.check_output('poff -a',shell=True)
    except BaseException,e:
        logger.info('exception occurs when turn off the ppp')


class LED(object):
    red = 14
    yellow = 18
    white = 15
    def __init__(self):
        self.red = 14
        self.white = 15
        self.yellow = 18
        self.states = {LED.red:False,LED.yellow:False,LED.white:False}
        self.led_init()

    def led_init(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(14,GPIO.OUT)
        GPIO.setup(15,GPIO.OUT)
        GPIO.setup(18,GPIO.OUT)
    
    def led_set(self,led,state):
        assert state == True or state == False
        assert led in self.states.keys()
        if state != self.states[led] :
            self.states[led] = state
            GPIO.output(led,state)

    def led_get(self,led):
        assert led in self.states.keys()
        return self.states[led]

    def clear(self):
        GPIO.cleanup()

    def twinkle(self,led,n=10):
        for i in range(n):
            self.led_set(led,True)
            time.sleep(0.3)
            self.led_set(led,False)
            time.sleep(0.3)

def t_checkap():
    global exist
    global exist_old
    global time_on
    global lock
    while(not stop_event.isSet()):
        exist = client_exists()
        #client changed
        if exist != exist_old :
            if exist == True :
                print 'start to connect pppoe'
                connect()
                lock.acquire()
                time_on = 0
                lock.release()
            elif exist == False :
                print 'close pppoe'
                disconnect()
                lock.acquire()
                time_on = 0
                lock.release()

            exist_old = exist

        #time count
        if exist == True :  
            time.sleep(5)
            lock.acquire()
            time_on += 5
            lock.release()
        
        #disconnect when time up
        if time_on >= TIME_UP and time_on <= TIME_UP + 10 :
            logger.info('time up, close the connection')
            disconnect() 


def t_ledshow():
    #only read time_on and changed the light according to the time_on
    global time_on
    while(not stop_event.isSet()):
        if exist == False:
            led.led_set(LED.red,False)
            
        elif exist == True:
            if time_on <= TIME_UP :
                led.led_set(LED.red,True)
                
            elif time_on > TIME_UP: 
                led.led_set(LED.red,False)

            if time_on > TIME_UP-30 and time_on <= TIME_UP :
                led.twinkle(LED.white,10)    

        time.sleep(3)


def button_init():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(23,GPIO.IN,GPIO.PUD_UP)
    GPIO.add_event_detect(23,GPIO.FALLING,button_down,1)


def button_down(channel):
    global lock
    global time_on
    logger.info('the button down, the time renewed')

    if time_on <= TIME_UP:
        lock.acquire()
        time_on = 0
        lock.release()

    else:
        lock.acquire()
        time_on = 0
        lock.release()
        connect()


def button_clear():
    GPIO.cleanup(23)


def sigint_handler(signum,frame):
    logger.info('Ctrl+C is pressed')
    stop_event.set()
    led.clear() 
    button_clear()
    disconnect()



if __name__ == '__main__':
    signal.signal(signal.SIGINT,sigint_handler)
    led = LED()
    led.led_set(LED.red,True)
    button_init() 
    t_check = threading.Thread(target=t_checkap)
    t_check.setDaemon(True)
    t_led = threading.Thread(target=t_ledshow)
    t_led.setDaemon(True)
    t_check.start()
    t_led.start()
    while True:
        time.sleep(1)
    t_check.join()
    t_led.join()

