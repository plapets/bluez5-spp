
# June 24 2019 Peter Lapets
# Trivial Serial Port Profile server for Bluez 5
#
# Released under GPLv3, I guess.
# Haven't implemented sending stuff to the client, but that's easy to add...
#
# https://github.com/tonyespy/bluez5-spp-example

import socket

# sudo apt-get install libgirepository1.0-dev 
# pip3 install pygobject
from gi.repository import GLib

# git clone -b master+async+unixfd --single-branch https://github.com/molobrakos/pydbus.git
# cd pydbus
# pip3 install .
from pydbus import SystemBus

# At the time of writing, pydbus has a bug.  The returned file
# handle (see below) is copied rather than passed over, causing
# a leak where two file objects are created but only one is
# destroyed.
#
# I have fixed this but not yet put the change on github.

"""
it is necessary to create a file /etc/dbus-1/system-local.conf
with the contents:

<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
"http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
    <policy context="default">
        <allow own="lapets.bluetooth.serial"/>
    </policy>
</busconfig>

it MAY also be necessary to usermod -aG bluetooth user
"""


# define a Bluez Profile1 interface
class BluezServiceProfile1(object):
    """
    <node>
        <interface name="org.bluez.Profile1">
            <method name="NewConnection">
                <arg direction="in" type="o"        name="device"       />
                <arg direction="in" type="h"        name="fd"           />
                <arg direction="in" type="a{sv}"    name="fd_properties"/>
            </method>

            <method name="RequestDisconnection">
                <arg direction="in" type="o" name="device"/>
            </method>

            <method name="Release">
            </method>
        </interface>
    </node>
    """

    def NewConnection(self, device, fd, fd_properties):
        pass

    def RequestDisconnection(self, device):
        pass

    def Release(self):
        pass


class Singleton:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls, *args, **kwargs)
        return cls._instance


class BluezServerApplication(BluezServiceProfile1, Singleton):
    # need to inherit the interface's docstring to publish on DBus
    __doc__ = BluezServiceProfile1.__doc__

    BUFFER_SIZE = 1024
    glib_watch_tags = []

    def io_rw_callback(self, fd, condition):
        print(self.sock.recv(self.BUFFER_SIZE).strip().decode('utf-8'))
        return True

    def io_close_callback(self, fd, condition):
        # remove event sources for the closing socket
        for tag in self.glib_watch_tags:
            GLib.source_remove(tag)
        self.glib_watch_tags = []

        print('Closing socket...')
        self.sock.close()

    def NewConnection(self, device, fd, fd_properties):
        self.sock = socket.socket(fileno=fd)

        # have GLib call our handler when I/O happens on fd
        # store the return values in an array to release later
        self.glib_watch_tags =  [   GLib.io_add_watch(fd, GLib.IO_PRI,  self.io_rw_callback),
                                    GLib.io_add_watch(fd, GLib.IO_IN,   self.io_rw_callback),
                                ]
        GLib.io_add_watch(fd, GLib.IO_HUP,  self.io_close_callback)

        print('%s connected on socket %s (%s)' %    (   str(device),
                                                        str(fd),
                                                        str(fd_properties)
                                                    ))

    def RequestDisconnection(self, device):
        print('Bluez requests disconnect.')

    def Release(self):
        print('Bluez called Profile1.Release() .')

    def Start(self):
        bus = SystemBus()

        # publish our own Bluez 5 Profile1 interface on the system DBus
        bus.publish('lapets.bluetooth.serial', self)

        # get a proxy object for org.bluez at path /org/bluez
        # using the interface org.bluez.ProfileManager1
        profile_mgr = bus.get('org.bluez', '/org/bluez')['.ProfileManager1']

        # tell Bluez that our interface implements the SPP protocol
        spp_obj_path    =   '/lapets/bluetooth/serial' 
        spp_uuid        =   '00001101-0000-1000-8000-00805f9b34fb'

        spp_options =   {   'Name':     GLib.Variant('s', 'BT Serial Port'),
                            'Role':     GLib.Variant('s', 'server'),
                            'Channel':  GLib.Variant('i', 6)
                        }

        try:
            profile_mgr.RegisterProfile(spp_obj_path, spp_uuid, spp_options)
        except GLib.Error as e:
            # unapologetic C-style profanity
            switch =    {   36 : lambda err: print("Service profile already exists!\n(GLib says: %s)" % str(err))
                        }
            if e.code in switch:
                switch[e.code](e)
            else:
                raise

        print('Awaiting connection...')

        loop = GLib.MainLoop()
        loop.run()


if '__main__' == __name__:
    bluetoothServer = BluezServerApplication()
    bluetoothServer.Start()

