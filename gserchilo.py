#!/usr/bin/env python

import sys
import os
import gtk
import re
import urllib
import urllib2
import subprocess
import ConfigParser

class SerchiloAPI(object):

	def __init__(self, language, country, user, namespaces):
		self.api_url = "http://www.serchilo.net/url/n/%s?keyword=%s&argument_count=%i"
		self.search_url = "http://www.serchilo.net/n/%s?query=%s&default_keyword="

		self.language = language
		self.country = country
		self.user = user
		self.namespaces = namespaces

	def query(self, query):
		"""Call Serchilo API with query and replace placeholders. No exceptions will be catched."""
		# TODO: user stuff
		language = None
		country = None
		query_split = query.split(" ")
		keyword = query_split[0]
		namespaces = []
		if keyword.find(".") >= 0:
			# namespace was enforced within the query
			forced_namespace = keyword.split(".")[0]
			if len(forced_namespace) == 2:
				language = forced_namespace
			elif len(forced_namespace) == 3:
				country = forced_namespace
		if self.namespaces != None:
			# configured namespaced will always be prepended
			namespaces = namespaces + self.namespaces
		if language == None:
			# language will be prepended if it wasn't enforced within the query
			namespaces = [self.language] + namespaces
			language = self.language
		if country == None:
			# country will be prepended if it wasn't enforced within the query
			namespaces = [self.country] + namespaces
			country = self.country
		
		if len(query_split) > 1 and query_split[1] != "":
			arguments = (" ".join(query_split[1:])).split(",")
		else:
			# query without arguments
			arguments = []

		url = self.api_url % (".".join(namespaces), keyword, len(arguments))
		f = urllib2.urlopen(url)
		# (if an exceptions occurs it will be passwd to the caller)
		result = f.read()
		if not result:
			# empty response (query not found/...)
			return None

		# TODO: are there other additional placeholders (user/userid/...)?
		result = result.replace("{language}", language)
		result = result.replace("{country}", country)
		placeholders = list(re.finditer("(\{s:[^\}]+\})", result))

		if len(arguments) > len(placeholders):
			# use excess arguments for placeholder (will allow stuff like "g berlin,germany,blah")
			arguments[len(placeholders)-1] = ",".join(arguments[len(placeholders)-1:])

		for i in range(0, len(placeholders)):
			placeholder = placeholders[i].group(1)
			result = result.replace(placeholder, arguments[i])

		return result

	def get_search_url(self, query):
		return self.search_url % (".".join(self.namespaces), urllib.quote_plus(query))

class GSerchilo(object):

	def __init__(self):
		self.job_active = False
		self.builder = gtk.Builder()
		self.builder.add_from_file(os.path.dirname(os.path.realpath(__file__)) + os.sep + "main.ui") # TODO: Where to put it for packaging?
		self.builder.connect_signals(self)
		self.queryentry = self.o("queryentry")
		self.submitbutton = self.o("submitbutton")

		# defaults
		self.settings = {
			"language": "en",
			"country": "usa",
			"user": None,
			"namespaces": None,
			"browser": "x-www-browser"
		}
		self.config_section = "gserchilo"
		# try to read settings
		# TODO: Best practice for storing configs? windows/osx environment?
		configfile = os.path.expanduser('~/.config/gserchilo/default.conf')
		try:
			if os.path.isfile(configfile):
				config = ConfigParser.ConfigParser()
				config.readfp(open(configfile))
				for key in self.settings.keys():
					if config.has_option(self.config_section, key):
						self.settings[key] = config.get(self.config_section, key)
		except Exception as e:
			print "Unable to parse config: %s" % e

		self.api = SerchiloAPI(self.settings["language"], self.settings["country"], self.settings["user"], [] if self.settings["namespaces"] == None else self.settings["namespaces"].split("."))

		# namespaces listing
		namespaces = [self.settings["language"], self.settings["country"]]
		if self.settings["namespaces"] != None:
			namespaces += self.settings["namespaces"].split(".")
		markup = ""
		for n in namespaces:
			markup += '<span background="#aa2c30" foreground="#ffffff">%s</span> ' % n

		box = self.o("hbox1")
		namespace_label = gtk.Label()
		box.add(namespace_label)
		namespace_label.set_markup(markup)
		namespace_label.show()

	def o(self, name):
		return self.builder.get_object(name)

	def run(self):
		try:
			gtk.gdk.threads_init()
			gtk.main()
		except KeyboardInterrupt:
			pass

	def submit(self):
		self.sensitive(False)

		query = self.queryentry.get_text()

		try:
			redirect_url = self.api.query(query)
		except Exception as e:
			dialog = gtk.MessageDialog(type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK, message_format="Exception occured: %s" % e)
			dialog.run()
			dialog.destroy()
			self.sensitive(True)
			return
		if not redirect_url:
			dialog = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, message_format="No URL for redirect received. Initiate Serchilo search (non-privacy mode)?")
			response = dialog.run()
			dialog.destroy()
			if response == gtk.RESPONSE_YES:
				redirect_url = self.api.get_search_url(query)
			else:
				self.queryentry.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse("red"))
				self.sensitive(True)
				return

		try:
			process = subprocess.Popen([self.settings["browser"], redirect_url], shell=False)
			self.quit()
		except Exception as e:
			dialog = gtk.MessageDialog(type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK, message_format="Unable to launch browser: %s" % e)
			dialog.run()
			dialog.destroy()

	def quit(self):
		gtk.main_quit()

	def sensitive(self, sensitive):
		self.queryentry.set_sensitive(sensitive)
		self.submitbutton.set_sensitive(sensitive)
		if (sensitive):
			self.queryentry.grab_focus()

	# signal handlers

	def on_queryentry_key_press_event(self, widget, event, *args):
		self.queryentry.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse("white"))
		if gtk.gdk.keyval_name(event.keyval) in ["Return", "KP_Enter"]:
			self.submit()
		elif gtk.gdk.keyval_name(event.keyval) == "Escape":
			self.quit()

	def on_submitbutton_clicked(self, *args):
		self.submit()

	def on_mainwindow_delete_event(self, *args):
		self.quit()

if __name__ == "__main__":
	GSerchilo().run()

