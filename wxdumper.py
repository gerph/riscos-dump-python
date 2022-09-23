#!/usr/bin/env python
"""
Hex dump display of files, as a WxPython application.

This is really just a simple harness to test that the dump library works.
"""

import os
import textwrap

import wx
import wx.adv

import wxdump


app_name = "Hex Dumper"
app_version = '0.01'
app_date = '15 Sep 2022'
app_description = "Display contents of files"
app_copyright = "(C) Gerph, 2022"
app_website = "https://github.com/gerph/riscos-dump-python"
app_license = open(os.path.join(os.path.dirname(__file__), 'LICENSE'), 'r').read()


class MainFrame(wx.Frame):

    def __init__(self, app, title="Hex Dumper"):
        super(MainFrame, self).__init__(None, -1, title=title)
        self.app = app

        MenuBar = wx.MenuBar()

        FileMenu = wx.Menu()

        item = FileMenu.Append(wx.ID_EXIT, "&Exit")
        self.Bind(wx.EVT_MENU, self.OnQuit, item)

        item = FileMenu.Append(wx.ID_ANY, "&Open file...")
        self.Bind(wx.EVT_MENU, self.OnOpen, item)

        MenuBar.Append(FileMenu, "&File")

        HelpMenu = wx.Menu()

        item = HelpMenu.Append(wx.ID_ABOUT, "&About",
                               "More information about this program")
        self.Bind(wx.EVT_MENU, self.OnAbout, item)
        MenuBar.Append(HelpMenu, "&Help")

        self.SetMenuBar(MenuBar)

        btn = wx.Button(self, label = "Quit")
        btn.Bind(wx.EVT_BUTTON, self.OnQuit)

        self.Bind(wx.EVT_CLOSE, self.OnQuit)

    def OnQuit(self,Event):
        self.Destroy()

    def OnAbout(self, event):
        info = wx.adv.AboutDialogInfo()
        info.SetName(app_name)
        info.SetVersion('{} ({})'.format(app_version,
                                         app_date))
        info.SetDescription(app_description)
        info.SetCopyright(app_copyright)
        info.SetWebSite(app_website)
        license = textwrap.wrap(app_license.replace('\n', ' '))
        info.SetLicense('\n'.join(license))

        wx.adv.AboutBox(info)

    def OnOpen(self, event):
        dlg = wx.FileDialog(self, message="Choose a file",
                           defaultDir=os.getcwd(),
                           defaultFile="",
                           style=wx.FD_OPEN |
                                 wx.FD_CHANGE_DIR | wx.FD_FILE_MUST_EXIST)

        if dlg.ShowModal() == wx.ID_OK:
            self.app.OpenFileMessage(dlg.GetPath())


class MyApp(wx.App):
    def __init__(self, *args, **kwargs):
        wx.App.__init__(self, *args, **kwargs)

        # This catches events when the app is asked to activate by some other
        # process
        self.Bind(wx.EVT_ACTIVATE_APP, self.OnActivate)

    def OnInit(self):
        frame = MainFrame(self)
        frame.Show()

        import sys
        for f in  sys.argv[1:]:
            self.OpenFileMessage(f)

        return True

    def BringWindowToFront(self):
        try: # it's possible for this event to come when the frame is closed
            self.GetTopWindow().Raise()
        except:
            pass

    def OnActivate(self, event):
        # if this is an activate event, rather than something else, like iconize.
        if event.GetActive():
            self.BringWindowToFront()
        event.Skip()

    def OpenFileMessage(self, filename):
        print("Open %s" % (filename,))

        def dummy_menu_item(grid, dump, chosen=False):
            print("Dummy menu entry chosen")

        config = wxdump.WxDumpConfigDark()
        config.cellinfo=lambda offset: 'Offset %i' % (offset,)
        config.menu_extra=[('Dummy menu entry', dummy_menu_item)]
        config.dump_params = {
                                'columns': 16,
                                'width': 1,
                                'annotation_func': lambda grid, row, offset, address: 'Offset %i' % (offset,),
                                'annotations': True,
                             }
        config.frame_statusbar = True

        frame = wxdump.DumpFileFrame(filename,
                                     "Hex Dumper: {}".format(filename),
                                     config=config)
        frame.Show()

    def MacOpenFile(self, filename):
        self.OpenFileMessage(filename)

    def MacReopenApp(self):
        self.BringWindowToFront()


app = MyApp(False)
app.MainLoop()
