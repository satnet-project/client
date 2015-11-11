# coding=utf-8
"""
   Copyright 2015 Samuel Góngora García
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
:Author:
    Samuel Góngora García (s.gongoragarcia@gmail.com)
"""
__author__ = 's.gongoragarcia@gmail.com'


import sys
import getopt
import os
import misc

from PyQt4 import QtGui
from PyQt4 import QtCore

from Queue import Queue
from OpenSSL import SSL

from twisted.python import log
from twisted.internet import ssl

from twisted.internet.ssl import ClientContextFactory
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.protocols.amp import AMP
from twisted.internet.defer import inlineCallbacks

from ampCommands import Login
from ampCommands import StartRemote
from ampCommands import NotifyMsg
from ampCommands import NotifyEvent
from ampCommands import SendMsg

from gs_interface import GroundStationInterface
from gs_interface import OperativeUDPThread
from gs_interface import OperativeTCPThread
from gs_interface import OperativeKISSThread


class ClientProtocol(AMP):

    def __init__(self, CONNECTION_INFO, gsi):
        self.CONNECTION_INFO = CONNECTION_INFO
        self.gsi = gsi

    def connectionMade(self):
        self.user_login()
        self.gsi.connectProtocol(self)

    def connectionLost(self, reason):
        log.msg("Connection lost")
        self.gsi.disconnectProtocol()

    @inlineCallbacks
    def user_login(self):
        res = yield self.callRemote(Login,\
         sUsername=self.CONNECTION_INFO['username'],\
          sPassword=self.CONNECTION_INFO['password'])

        # if res['bAuthenticated'] == True:
        #     # log.msg('bAuthenticated True')
        #     res = yield self.callRemote(StartRemote,\
        #      iSlotId=self.CONNECTION_INFO['slot_id'])

        if res['bAuthenticated'] == True:
            # log.msg('bAuthenticated True')
            res = yield self.callRemote(StartRemote,\
             iSlotId='-1')

        elif res['bAuthenticated'] == False:
            log.msg('False')

        else:
            log.msg('No data')

        # d = self.callRemote(Login, sUsername=self.CONNECTION_INFO['username'],\
        #  sPassword=self.CONNECTION_INFO['password'] )
        # def connected(self):
        #     self.callRemote(StartRemote,\
        #      iSlotId=self.CONNECTION_INFO['slot_id'])
        # d.addCallback(connected, self)
        # def notConnected(failure):
        #     log.err("Error during connection")
        # d.addErrback(notConnected)
        # return d

    def vNotifyMsg(self, sMsg):
        log.msg("(" + self.CONNECTION_INFO['username'] +\
         ") --------- Notify Message ---------")
        log.msg(sMsg)
        if self.CONNECTION_INFO['connection'] == 'serial':        
            self.kissTNC.write(sMsg)        
        elif self.CONNECTION_INFO['connection'] == 'udp':
            self.UDPSocket.sendto(sMsg, (self.CONNECTION_INFO['ip'],\
             self.CONNECTION_INFO['udpport']))
        elif self.CONNECTION_INFO['connection'] == 'tcp':
            self.TCPSocket.send(sMsg)

        return {}
    NotifyMsg.responder(vNotifyMsg)

    # Method associated to frame processing.
    def _processframe(self, frame):
        self.processFrame(frame)

    @inlineCallbacks
    def processFrame(self, frame):

        log.msg('Received frame: ' + frame)
        yield self.callRemote(SendMsg, sMsg=frame,\
         iTimestamp=misc.get_utc_timestamp())

    def vNotifyEvent(self, iEvent, sDetails):
        log.msg("(" + self.CONNECTION_INFO['username'] +\
         ") --------- Notify Event ---------")
        if iEvent == NotifyEvent.SLOT_END:
            log.msg("Disconnection because the slot has ended")
        elif iEvent == NotifyEvent.REMOTE_DISCONNECTED:
            log.msg("Remote client has lost the connection")
        elif iEvent == NotifyEvent.END_REMOTE:
            log.msg("The remote client has closed the connection")
        elif iEvent == NotifyEvent.REMOTE_CONNECTED:
            log.msg("The remote client has just connected")

        return {}
    NotifyEvent.responder(vNotifyEvent)


class ClientReconnectFactory(ReconnectingClientFactory):
    """
    ReconnectingClientFactory inherited object class to handle the 
    reconnection process.
    """
    def __init__(self, CONNECTION_INFO, gsi):
        self.CONNECTION_INFO = CONNECTION_INFO
        self.gsi = gsi

    # Called when a connection has been started
    def startedConnecting(self, connector):
        log.msg("Starting connection..........................." +\
         "..........................." + "..........................." +\
          "........................")

    # Create an instance of a subclass of Protocol
    def buildProtocol(self, addr):
        log.msg("Building protocol.............................." +\
         "................................................................")
        self.resetDelay()
        return ClientProtocol(self.CONNECTION_INFO, self.gsi)

    # Called when an established connection is lost
    def clientConnectionLost(self, connector, reason):
        if self.CONNECTION_INFO['reconnection'] == 'yes':
            self.continueTrying = True
        elif self.CONNECTION_INFO['reconnection'] == 'no':
            self.continueTrying = None

        log.msg('Lost connection. Reason: ', reason)
        ReconnectingClientFactory.clientConnectionLost(self,\
         connector, reason)

    # Called when a connection has failed to connect
    def clientConnectionFailed(self, connector, reason):
        if self.CONNECTION_INFO['reconnection'] == 'yes':
            self.continueTrying = True
        elif self.CONNECTION_INFO['reconnection'] == 'no':
            self.continueTrying = None

        log.msg('Connection failed. Reason: ', reason)
        ReconnectingClientFactory.clientConnectionFailed(self,\
         connector, reason)


class CtxFactory(ClientContextFactory):

    def getContext(self):
        self.method = SSL.SSLv23_METHOD
        ctx = ssl.ClientContextFactory.getContext(self)

        return ctx


class Client(object):
    """
    This class starts the client using the data provided by user interface.
    :ivar CONNECTION_INFO:
        This variable contains the following data: username, password, slot_id, 
        connection (either 'serial' or 'udp'), serialport, baudrate, ip, port.
    :type CONNECTION_INFO:
        L{Dictionary}
    :ivar
    """
    def __init__(self, CONNECTION_INFO):
        self.CONNECTION_INFO = CONNECTION_INFO

    def createConnection(self):
        # New interface
        gsi = GroundStationInterface(self.CONNECTION_INFO, "Vigo",\
         ClientProtocol)

        global connector

        connector = reactor.connectSSL('localhost', 1234,\
         ClientReconnectFactory(self.CONNECTION_INFO, gsi),\
          CtxFactory())

        return gsi, connector


# QDialog, QWidget or QMainWindow, which is better in this situation? TO-DO
class SATNetGUI(QtGui.QWidget):
    def __init__(self, parent = None):
        QtGui.QWidget.__init__(self, parent)

        self.initUI()
        self.initButtons()
        self.initFields()
        self.initLogo()
        self.initData()
        self.initConsole()
        self.serialSignal = True
        self.UDPSignal = True
        self.TCPSignal = True

        self.serial_queue = Queue()
        self.udp_queue = Queue()
        self.tcp_queue = Queue()

    # Run threads associated to KISS protocol
    def runKISSThread(self):
        self.workerKISSThread = OperativeKISSThread(self.serial_queue,\
            self.sendData, self.serialSignal)
        self.workerKISSThread.start()

    # Run threads associated to UPD protocol
    def runUDPThread(self):
        self.workerUDPThread = OperativeUDPThread(self.udp_queue,\
         self.sendData, self.UDPSignal)
        self.workerUDPThread.start()
        
    # Run threads associated to TCP protocol
    def runTCPThread(self):
        self.workerTCPThread = OperativeTCPThread(self.tcp_queue,\
         self.sendData, self.TCPSignal)
        self.workerTCPThread.start()
    
    # Stop KISS thread
    def stopKISSThread(self):
        self.workerKISSThread.stop()

    # Stop UDP thread
    def stopUDPThread(self):
        self.workerUDPThread.stop()
        
    # Stop TCP thread
    def stopTCPThread(self):
        self.workerTCPThread.stop()
        
    # Gets a string but can't format it! To-do
    def sendData(self, result):
        self.gsi._manageFrame(result)

    # Create a new connection by loading the connection parameters
    # from the interface window
    def NewConnection(self):
        self.CONNECTION_INFO = {}

        self.CONNECTION_INFO['username'] = str(self.LabelUsername.text())
        self.CONNECTION_INFO['password'] = str(self.LabelPassword.text())
        self.CONNECTION_INFO['slot_id'] = int(self.LabelSlotID.text())
        self.CONNECTION_INFO['connection'] =\
         str(self.LabelConnection.currentText())
        self.CONNECTION_INFO['serialport'] =\
         str(self.LabelSerialPort.currentText())
        self.CONNECTION_INFO['baudrate'] = str(self.LabelBaudrate.text())
        self.CONNECTION_INFO['ip'] = self.LabelUDP.text()
        # print self.LabelUDPPort.text()
        self.CONNECTION_INFO['udpport'] = int(self.LabelUDPPort.text())
        self.CONNECTION_INFO['tcpport'] = int(self.LabelUDPPort.text())


        self.CONNECTION_INFO['reconnection'],\
         self.CONNECTION_INFO['parameters'] = self.LoadSettings()

        self.gsi, self.c = Client(self.CONNECTION_INFO).createConnection()

        # Start the selected connection
        self.connectionkind = self.CheckConnection()
        if self.connectionkind == 'serial':
            self.runKISSThread()
        elif self.connectionkind == 'udp':
            self.runUDPThread()
        elif self.connectionkind == 'tcp':
            self.runTCPThread()
            
        else:
            log.err('Error choosing connection type')

        self.ButtonNew.setEnabled(False)
        self.ButtonCancel.setEnabled(True)

        self.LoadDefaultSettings.setEnabled(False)
        self.AutomaticReconnection.setEnabled(False)


    def initUI(self):
        QtGui.QToolTip.setFont(QtGui.QFont('SansSerif', 10))
        self.setFixedSize(1300, 800)
        self.setWindowTitle("SATNet client - Generic")

    def initButtons(self):
        # Control buttons.
        buttons = QtGui.QGroupBox(self)
        grid = QtGui.QGridLayout(buttons)
        buttons.setLayout(grid)

        # New connection.
        self.ButtonNew = QtGui.QPushButton("Connection")
        self.ButtonNew.setToolTip("Start a new connection using the " +\
         "selected connection")
        self.ButtonNew.setFixedWidth(145)
        self.ButtonNew.clicked.connect(self.NewConnection)
        # Close connection.
        self.ButtonCancel = QtGui.QPushButton("Disconnection")
        self.ButtonCancel.setToolTip("End current connection")
        self.ButtonCancel.setFixedWidth(145)
        self.ButtonCancel.clicked.connect(self.CloseConnection)
        self.ButtonCancel.setEnabled(False)
        # Load parameters from file
        ButtonLoad = QtGui.QPushButton("Load parameters from file")
        ButtonLoad.setToolTip("Load parameters from <i>config.ini</i> file")
        ButtonLoad.setFixedWidth(298)
        ButtonLoad.clicked.connect(self.LoadParameters)
        # Configuration
        ButtonConfiguration = QtGui.QPushButton("Configuration")
        ButtonConfiguration.setToolTip("Open configuration window")
        ButtonConfiguration.setFixedWidth(145)
        ButtonConfiguration.clicked.connect(self.SetConfiguration)
        # Help.
        ButtonHelp = QtGui.QPushButton("Help")
        ButtonHelp.setToolTip("Click for help")
        ButtonHelp.setFixedWidth(145)
        ButtonHelp.clicked.connect(self.usage)
        grid.addWidget(self.ButtonNew, 0, 0, 1, 1)
        grid.addWidget(self.ButtonCancel, 0, 1, 1, 1)
        grid.addWidget(ButtonLoad, 1, 0, 1, 2)
        grid.addWidget(ButtonConfiguration, 2, 0, 1, 1)
        grid.addWidget(ButtonHelp, 2, 1, 1, 1)
        buttons.setTitle("Connection")
        buttons.move(10, 10)

    def initFields(self):
        # Parameters group.
        parameters = QtGui.QGroupBox(self)
        layout = QtGui.QFormLayout()
        parameters.setLayout(layout)

        self.LabelUsername = QtGui.QLineEdit()
        self.LabelUsername.setFixedWidth(190)
        layout.addRow(QtGui.QLabel("Username:       "), self.LabelUsername)
        self.LabelPassword = QtGui.QLineEdit()
        self.LabelPassword.setFixedWidth(190)
        self.LabelPassword.setEchoMode(QtGui.QLineEdit.Password)
        layout.addRow(QtGui.QLabel("Password:       "), self.LabelPassword)
        self.LabelSlotID = QtGui.QSpinBox()
        layout.addRow(QtGui.QLabel("slot_id:        "), self.LabelSlotID)

        self.LabelConnection = QtGui.QComboBox()
        self.LabelConnection.addItems(['serial', 'udp', 'tcp'])
        self.LabelConnection.activated.connect(self.CheckConnection)
        layout.addRow(QtGui.QLabel("Connection:     "), self.LabelConnection)
        self.LabelSerialPort = QtGui.QComboBox()
        from glob import glob
        ports = glob('/dev/tty[A-Za-z]*')
        self.LabelSerialPort.addItems(ports)
        layout.addRow(QtGui.QLabel("Serial port:    "), self.LabelSerialPort)
        self.LabelBaudrate = QtGui.QLineEdit()
        layout.addRow(QtGui.QLabel("Baudrate:       "), self.LabelBaudrate)
        self.LabelUDP = QtGui.QLineEdit()
        layout.addRow(QtGui.QLabel("Host:            "), self.LabelUDP)
        self.LabelUDPPort = QtGui.QLineEdit()
        layout.addRow(QtGui.QLabel("Port:       "), self.LabelUDPPort)

        parameters.setTitle("User data")
        parameters.move(10, 145)

        # Configuration group.
        configuration = QtGui.QGroupBox(self)
        configurationLayout = QtGui.QVBoxLayout()
        configuration.setLayout(configurationLayout)

        self.LoadDefaultSettings =\
         QtGui.QCheckBox("Automatically load settings from 'config.ini'")
        configurationLayout.addWidget(self.LoadDefaultSettings)
        self.AutomaticReconnection =\
         QtGui.QCheckBox("Reconnect after a failure")
        configurationLayout.addWidget(self.AutomaticReconnection)

        configuration.setTitle("Basic configuration")
        configuration.move(10, 400)

    def initLogo(self):
        # Logo.
        self.LabelLogo = QtGui.QLabel(self)
        self.LabelLogo.move(20, 490)
        pic = QtGui.QPixmap(os.getcwd() + "/logo.png")
        self.LabelLogo.setPixmap(pic)
        self.LabelLogo.show()

    def initData(self):
        reconnection, parameters = self.LoadSettings()
        if reconnection == 'yes':
            self.AutomaticReconnection.setChecked(True)
        elif reconnection == 'no':
            self.AutomaticReconnection.setChecked(False)
        if parameters == 'yes':
            self.LoadDefaultSettings.setChecked(True)
            self.LoadParameters()
        elif parameters == 'no':
            self.LoadDefaultSettings.setChecked(False)

    def initConsole(self):
        # Console
        self.console = QtGui.QTextBrowser(self)
        self.console.move(340, 10)
        self.console.resize(950, 780)
        self.console.setFont(QtGui.QFont('SansSerif', 10))

    # To-do Not closed properly.
    def CloseConnection(self):
        if self.connectionkind == 'udp':
            try:
                self.stopUDPThread()
                log.msg("Stopping UDP connection")
            except Exception as e:
                log.err(e)
                log.err("Can't stop UDP thread")
        if self.connectionkind == 'tcp':
            try:
                self.stopTCPThread()
                log.msg("Stopping TCP connection")
            except Exception as e:
                log.err(e)
                log.err("Can't stop TCP thread")

        elif self.connectionkind == 'serial':
            try:
                self.stopKISSThread()
                log.msg("Stopping KISS connection")
            except Exception as e:
                log.err(e)
                log.err("Can't stop KISS thread")

        else:
            raise Exception

        self.c.disconnect()

        self.ButtonNew.setEnabled(True)
        self.ButtonCancel.setEnabled(False)

    # Load settings from .settings file.
    def LoadSettings(self):
        import ConfigParser
        config = ConfigParser.ConfigParser()
        config.read(".settings")

        reconnection = config.get('Connection', 'reconnection')
        parameters = config.get('Connection', 'parameters')

        return reconnection, parameters

    # Load connection parameters from config.ini file.
    def LoadParameters(self):
        self.CONNECTION_INFO = {}

        import ConfigParser
        config = ConfigParser.ConfigParser()
        config.read("config.ini")

        self.CONNECTION_INFO['username'] = config.get('User', 'username')
        self.LabelUsername.setText(self.CONNECTION_INFO['username'])
        self.CONNECTION_INFO['password'] = config.get('User', 'password')
        self.LabelPassword.setText(self.CONNECTION_INFO['password'])
        self.CONNECTION_INFO['slot_id'] = config.get('User', 'slot_id')
        self.LabelSlotID.setValue(int(self.CONNECTION_INFO['slot_id']))        
        self.CONNECTION_INFO['connection'] = config.get('User', 'connection')
        index = self.LabelConnection.findText(self.CONNECTION_INFO['connection'])
        self.LabelConnection.setCurrentIndex(index)

        self.CONNECTION_INFO['serialport'] = config.get('Serial',\
         'serialport')
        index = self.LabelSerialPort.findText(self.CONNECTION_INFO['serialport'])
        self.LabelSerialPort.setCurrentIndex(index)
        self.CONNECTION_INFO['baudrate'] = config.get('Serial',\
         'baudrate')
        self.LabelBaudrate.setText(self.CONNECTION_INFO['baudrate'])
        self.CONNECTION_INFO['ip'] = config.get('UDP', 'ip')
        self.LabelUDP.setText(self.CONNECTION_INFO['ip'])
        self.CONNECTION_INFO['udpport'] = int(config.get('UDP',\
         'udpport'))
        self.LabelUDPPort.setText(config.get('UDP', 'udpport'))

        if self.CONNECTION_INFO['connection'] == 'serial':
            self.LabelSerialPort.setEnabled(True)
            self.LabelBaudrate.setEnabled(True)
            self.LabelUDP.setEnabled(False)
            self.LabelUDPPort.setEnabled(False)

        else:
            self.LabelSerialPort.setEnabled(False)
            self.LabelBaudrate.setEnabled(False)
            self.LabelUDP.setEnabled(True)
            self.LabelUDPPort.setEnabled(True)

    def SetConfiguration(self):
        # First draft
        client, attempts = DateDialog.buildWindow()
        log.msg("Client name", client)
        log.msg("Attemps", attempts)

    def CheckConnection(self):
        Connection = str(self.LabelConnection.currentText())

        if Connection == 'serial':
            self.LabelSerialPort.setEnabled(True)
            self.LabelBaudrate.setEnabled(True)
            self.LabelUDP.setEnabled(False)
            self.LabelUDPPort.setEnabled(False)
        else:
            self.LabelSerialPort.setEnabled(False)
            self.LabelBaudrate.setEnabled(False)
            self.LabelUDP.setEnabled(True)
            self.LabelUDPPort.setEnabled(True)

        return Connection

    def usage(self):        
        print ("\n"
                "USAGE of client_amp.py\n"               
                "Usage: python client_amp.py [-u <username>] # Set SATNET username to login\n"
                "Usage: python client_amp.py [-p <password>] # Set SATNET user password to login\n"
                "Usage: python client_amp.py [-t <slot_ID>] # Set the slot id corresponding to the pass you will track\n"
                "Usage: python client_amp.py [-c <connection>] # Set the type of interface with the GS (serial or udp)\n"
                "Usage: python client_amp.py [-s <serialport>] # Set serial port\n"
                "Usage: python client_amp.py [-b <baudrate>] # Set serial port baudrate\n"
                "Usage: python client_amp.py [-i <ip>] # Set ip direction\n"
                "Usage: python client_amp.py [-u <udpport>] # Set udp port\n"
                "\n"
                "Example for serial config: python client_amp.py -g -u crespo -p cre.spo -t 2 -c serial -s /dev/ttyS1 -b 115200\n"
                "Example for udp config: python client_amp.py -g -u crespo -p cre.spo -t 2 -c udp -i 127.0.0.1 -u 5001\n"
                "\n"
                "[User]\n"
                "username: crespo\n"
                "password: cre.spo\n"
                "slot_id: 2\n"
                "connection: udp\n"
                "[Serial]\n"
                "serialport: /dev/ttyUSB0\n"
                "baudrate: 9600\n"
                "[UDP]\n"
                "ip: 127.0.0.1\n"
                "udpport: 5005")

    def center(self):
        frameGm = self.frameGeometry()
        screen_pos = QtGui.QApplication.desktop().cursor().pos()
        screen = QtGui.QApplication.desktop().screenNumber(screen_pos)
        centerPoint = QtGui.QApplication.desktop().screenGeometry(screen).center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())

    # Functions designed to output information
    @QtCore.pyqtSlot(str)
    def append_text(self,text):
        self.console.moveCursor(QtGui.QTextCursor.End)
        self.console.insertPlainText(text)

    def closeEvent(self, event):       
        reply = QtGui.QMessageBox.question(self, 'Exit confirmation',
            "Are you sure to quit?", QtGui.QMessageBox.Yes | 
            QtGui.QMessageBox.No, QtGui.QMessageBox.No)

        # Non asynchronous way. Need to re implement this. TO-DO
        if reply == QtGui.QMessageBox.Yes:
            try:
                # Connector disconnected
                self.c.disconnect()
            except Exception as e:
                log.err(e)
                log.err("Can't disconnected connector", self.c)
                # Serial thread stopped

        if self.connectionkind == 'udp':
            try:
                self.stopUDPThread()
            except Exception as e:
                log.err(e)
                log.err("Can't stop UDP thread")

        elif self.connectionkind == 'tcp':
            try:
                self.stopTCPThread()
            except Exception as e:
                log.err(e)
                log.err("Can't stop TCP thread")

        elif self.connectionkind == 'serial':
            try:
                self.stopKISSThread()
            except Exception as e:
                log.err(e)
                log.err("Can't stop KISS thread")

        else:
            raise Exception

        try:
            reactor.stop()
            log.msg("Reactor stopped")
            event.accept()
        except Exception as e:
            log.err(e)
            log.err("Reactor not running.")
            event.ignore()


class DateDialog(QtGui.QDialog):
    def __init__(self, parent = None):
        super(DateDialog, self).__init__(parent)

        parameters = QtGui.QGroupBox(self)
        layout_parameters = QtGui.QFormLayout()
        parameters.setLayout(layout_parameters)

        self.LabelClientname = QtGui.QLineEdit()
        self.LabelClientname.setFixedWidth(190)
        layout_parameters.addRow(QtGui.QLabel("Client name:           "),\
         self.LabelClientname)
        self.LabelPassword = QtGui.QLineEdit()
        self.LabelPassword.setFixedWidth(190)
        layout_parameters.addRow(QtGui.QLabel("Reconnection attempts: "),\
         self.LabelPassword)

    def getConfiguration(self):
        configuration = [str(self.LabelClientname.text()),\
         str(self.LabelPassword.text())]

        return configuration

    # static method to create the dialog and return (client, attempts)
    @staticmethod
    def buildWindow(parent = None):
        dialog = DateDialog(parent)
        dialog.exec_()
        configuration = dialog.getConfiguration()

        return (configuration[0], configuration[1])


# Objects designed for output the information
class WriteStream(object):
    def __init__(self,queue):
        self.queue = queue

    def write(self, text):
        self.queue.put(text)

    def flush(self):
        pass


# A QObject (to be run in a QThread) which sits waiting for data to come 
# through a Queue.Queue().
# It blocks until data is available, and one it has got something from the 
# queue, it sends it to the "MainThread" by emitting a Qt Signal 
class MyReceiver(QtCore.QThread):
    mysignal = QtCore.pyqtSignal(str)

    def __init__(self,queue,*args,**kwargs):
        QtCore.QThread.__init__(self,*args,**kwargs)
        self.queue = queue

    @QtCore.pyqtSlot()
    def run(self):
        while True:
            text = self.queue.get()
            self.mysignal.emit(text)


class ResultObj(QtCore.QObject):
    def __init__(self, val):
        self.val = val


if __name__ == '__main__':

    try:
        if sys.argv[1] == '--help':
            import subprocess
            subprocess.call(["man", "./satnetclient.1"])

    except IndexError:
        # Create Queue and redirect sys.stdout to this queue
        queue = Queue()
        sys.stdout = WriteStream(queue)

        log.startLogging(sys.stdout)
        log.msg('------------------------------------------------- ' + \
         'SATNet - Generic client' +\
          ' -------------------------------------------------')

        qapp = QtGui.QApplication(sys.argv)
        app = SATNetGUI()
        app.setWindowIcon(QtGui.QIcon('logo.png'))
        app.show()

        # Create thread that will listen on the other end of the queue, and 
        # send the text to the textedit in our application
        my_receiver = MyReceiver(queue)
        my_receiver.mysignal.connect(app.append_text)
        my_receiver.start()

        from qtreactor import pyqt4reactor
        pyqt4reactor.install()

        from twisted.internet import reactor
        reactor.run()

        qapp.exec_()
