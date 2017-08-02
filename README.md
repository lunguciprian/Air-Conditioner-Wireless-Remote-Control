# Air-Conditioner-Wireless-Remote-Control

## SETUP

### [Installing LIRC](http://www.raspberry-pi-geek.com/Archive/2014/03/Controlling-your-Pi-with-an-infrared-remote/(offset)/2)

LIRC (Linux Infrared Remote Control) is a software package for Linux, which, according to the developers *…allows you to decode and send infra-red signals of many (but not all) commonly used remote controls.*

```
sudo apt-get update
sudo apt-get upgrade
sudo apt-get install lirc liblircclient-dev
```

You will then have the option to install the new packages; click Y to continue with the installation. Once the installation completes, you might get some warning messages saying No valid /etc/lirc/lircd.conf has been found or something similar; however, you can ignore these messages for now.

The next step is to set up the hardware config file.

```
sudo mcedit /etc/lirc/hardware.conf
```
This command should open the hardware configuration file with the nano text editor. You then need to edit the contents of this   file so that it looks exactly like the file shown bellow

```
# /etc/lirc/hardware.conf
#
# Arguments which will be used when launching lircd
LIRCD_ARGS="--uinput"

#Don't start lircmd even if there seems to be a good config file
#START_LIRCMD=false

#Don't start irexec, even if a good config file seems to exist.
#START_IREXEC=false

#Try to load appropriate kernel modules
LOAD_MODULES=true

# Run "lircd --driver=help" for a list of supported drivers.
DRIVER="default"
# usually /dev/lirc0 is the correct setting for systems using udev 
DEVICE="/dev/lirc0"
MODULES="lirc_rpi"

# Default configuration files for your hardware if any
LIRCD_CONF=""
LIRCMD_CONF=""
```

If you are running a standard version of Raspbian and you want LIRC to start automatically on boot, enter the following command:

```
sudo mcedit /etc/modules
```

This command will load the modules file (which lists the kernel modules to load at boot time) using the nano text editor. You   then need to add the following lines at the bottom of the file:

```
lirc_dev
lirc_rpi gpio_in_pin=18, gpio_in_pin=10
```

Pin 18 will be used to take the output from the IR sensor, pin 10 will be used to send IR pulse and pin 4 used by temperature   sensor.

Edit your /boot/config.txt file and add:

```
dtoverlay=lirc-rpi,gpio_in_pin=18,gpio_out_pin=10,debug=on
dtoverlay=w1-gpio,gpiopin=4
```

reboot your device

### Decode your Device remote controler IR pulses

In order to perform a quick test to see if LIRC is working properlly, you need to stop the LIRC daemon.

```
sudo /etc/init.d/lirc stop
```

Start mode2 to see the pulse/space length of infrared signals.

```
mode2 -d /dev/lirc0
```

[] aici console.img


