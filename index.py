import os, logging, wsgiref.handlers, datetime, random, math, string, urllib, csv, json, time

from google.appengine.ext import webapp, db
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from gaesessions import get_current_session
from google.appengine.api import urlfetch

LengthOfData = 48
LengthOfPractice=30
NumScenarios=2
rewardAmount = 6 # number of cents added/subtracted for a good/bad outcome





###############################################################################
###############################################################################
######################## Data Classes for Database ############################
###############################################################################
###############################################################################

class User(db.Model):
	usernum =			db.IntegerProperty()
	account = 			db.StringProperty()
	browser =			db.StringProperty()
	sex =				db.IntegerProperty()
	ethnicity =			db.IntegerProperty()
	race =				db.IntegerProperty()
	age = 				db.IntegerProperty()
	bonusAmt =			db.IntegerProperty()
	testOrder =			db.IntegerProperty() # 0 is memory first, 1 is causal first
	progress = 			db.IntegerProperty()


class ScenarioData(db.Model):
	# user/scenario stuff
	user  =				db.ReferenceProperty(User)
	account = 			db.StringProperty()
	usernum =			db.IntegerProperty()
	scenario = 			db.IntegerProperty()

	# visuals
	# in the story conditions these are drug names
	# in the monetary conditions, they are shapes
	var1_Left = 		db.StringProperty()
	var1_Right = 		db.StringProperty()

	# in the story conditions these are faces
	# in the monetary condition they are shapes
	var2_Left =			db.StringProperty()
	var2_Right =		db.StringProperty()

	# attention variables
	trialTime = 		db.IntegerProperty()
	attentionFails =	db.IntegerProperty()
	reloads = 			db.IntegerProperty()

	# actual data
	trialNumber = 		db.IntegerProperty()
	trialGuess = 		db.StringProperty()
	trialCorrect = 		db.StringProperty()
	profitImpact = 		db.IntegerProperty()
	valence = 			db.StringProperty() # within-subs condition; 0 means rare-positive, 1 means rare-negative
	condition = 		db.StringProperty() # between-subs cover story condition; monetary, story, combined


class FinalJudgmentData(db.Model):
	user  =				db.ReferenceProperty(User)
	account = 			db.StringProperty()
	usernum =			db.IntegerProperty()
	scenario = 			db.IntegerProperty()
	valence = 			db.StringProperty() # 0 means rare-positive
	condition = 		db.StringProperty() # monetary, story, combined

	# visuals
	# in the story conditions these are drug names
	# in the monetary conditions, they are shapes
	var1_Left = 		db.StringProperty()
	var1_Right = 		db.StringProperty()

	# in the story conditions these are faces
	# in the monetary condition they are shapes
	var2_Left =			db.StringProperty()
	var2_Right =		db.StringProperty()

	leftDrugRarity =	db.StringProperty()
	rightDrugRarity =	db.StringProperty()

	# if story condition
	leftDrugColor = 	db.StringProperty()
	rightDrugColor = 	db.StringProperty()

	# number of bad outcomes for each drug
	leftNumberBad =		db.IntegerProperty()
	rightNumberBad =	db.IntegerProperty()

	# given a good outcome, how many got the left drug?
	goodOutcomesLeft =	db.IntegerProperty()
	goodOutcomesRight =	db.IntegerProperty()
	badOutcomesLeft =	db.IntegerProperty()
	badOutcomesRight = 	db.IntegerProperty()

	# causal judgment; this is changing for E1
	# which drug is worse? higher numbers mean the right side is worse
	causalJudgment =	db.IntegerProperty()
	judgmentOrder =		db.IntegerProperty() # will have to make a code for this, list possible orders, assign one



#This stores the current number of participants who have ever taken the study.
#see https://developers.google.com/appengine/docs/pythondatastore/transactions
#could also use get_or_insert
#https://developers.google.com/appengine/docs/pythondatastore/modelclass#Model_get_or_insert
class NumOfUsers(db.Model):
	counter = db.IntegerProperty(default=0)


#Increments NumOfUsers ensuring strong consistency in the datastore
@db.transactional
def create_or_increment_NumOfUsers():
	obj = NumOfUsers.get_by_key_name('NumOfUsers', read_policy=db.STRONG_CONSISTENCY)
	if not obj:
		obj = NumOfUsers(key_name='NumOfUsers')
	obj.counter += 1
	x=obj.counter
	obj.put()
	return(x)



###############################################################################
###############################################################################
########################### From Book Don't Touch #############################
###############################################################################
###############################################################################
# One line had to be updated for Python 2.7
#http://stackoverflow.com/questions/16004135/python-gae-assert-typedata-is-stringtype-write-argument-must-be-string
# A helper to do the rendering and to add the necessary
# variables for the _base.htm template
def doRender(handler, tname = 'index.htm', values = { }):
	temp = os.path.join(
			os.path.dirname(__file__),
			'templates/' + tname)
	if not os.path.isfile(temp):
		return False
	# Make a copy of the dictionary and add the path and session
	newval = dict(values)
	newval['path'] = handler.request.path
#   handler.session = Session()
#   if 'username' in handler.session:
#      newval['username'] = handler.session['username']

	outstr = template.render(temp, newval)
	handler.response.out.write(unicode(outstr))  #### Updated for Python 2.7
	return True


###############################################################################
###############################################################################
###################### Handlers for Individual Pages ##########################
###############################################################################
###############################################################################

###############################################################################
################################ Ajax Handler #################################
###############################################################################

class AjaxHandler(webapp.RequestHandler):
	def get(self):
		que=db.Query(ScenarioData)
		que.order("usernum").order("trialNumber")
		d=que.fetch(limit=10000)
		doRender(self, 'ajax.htm',{'d':d})

	def post(self):
		self.session=get_current_session()

  		trialTime = int(self.request.get('timeInput'))
  		attentionFails = int(self.request.get('attentionFailsInput'))
		trialNumber = int(self.request.get('trialInput'))
		trialGuess = str(self.request.get('guessInput'))
		trialCorrect = str(self.request.get('correctInput')) # gives the correct answer (A or B)
		profitImpact = int(self.request.get('profitImpactInput'))
		totalBonus = int(self.request.get('runningBonusInput'))
		valence = self.request.get('valenceInput')
		self.session['trialNumber'] = int(self.request.get('trialNumberInput'))
		self.session['reloads'] = int(self.request.get('reloadsInput'))


		logging.info('RELOADS: '+str(self.session['reloads']))

		logging.info('BONUS!!!!!! '+str(totalBonus))


		if self.session['scenario'] == 0:
			self.session['BonusOne'] = totalBonus
		else:
			self.session['BonusTwo'] = totalBonus

		logging.info('BONUS TEST!' + str(self.session['BonusOne']))
		logging.info('SCENARIO IS '+str(self.session['scenario']))

		# how to check if there are example rows in the datastore
		que = db.Query(ScenarioData).filter('usernum =', self.session['usernum']).filter('scenario =', self.session['scenario']).filter('trialNumber =', trialNumber)
		results = que.fetch(limit=1000)

		# make all of the data items into 3-value arrays, then make a loop to put them in the datastore
		if (len(results) == 0):
			newajaxmessage = ScenarioData(
				user=self.session['userkey'],
				usernum = self.session['usernum'],
				account = self.session['account'],
				scenario = self.session['scenario'],
				trialTime = trialTime,
				attentionFails = attentionFails,
				trialNumber = trialNumber,
				reloads		= self.session['reloads'],
				trialGuess = trialGuess,
				trialCorrect = trialCorrect,
				profitImpact = profitImpact,
				valence = valence); # this is the match between position2 and frequency2; sent to this handler as 'rare-positive' or 'rare-negative'


			newajaxmessage.put()
			self.response.out.write(json.dumps(({'blah': 'blah'}))) # not sure what this does?

		else:

			obj = que.get()
			obj.user=self.session['userkey']
			obj.usernum = self.session['usernum']
			obj.account = self.session['account']
			obj.scenario = self.session['scenario']
			obj.trialTime = trialTime
			obj.attentionFails = attentionFails
			obj.trialNumber = trialNumber
			obj.reloads = self.session['reloads']
			obj.trialGuess = trialGuess
			obj.trialCorrect = trialCorrect
			obj.profitImpact = profitImpact
			obj.valence = valence

			obj.put()
			self.response.out.write(json.dumps(({'blah': 'blah'}))) # ?

		que2 = db.Query(User).filter('usernum =', self.session['usernum'])
		results = que2.fetch(limit=10000)

		obj = que2.get()

		obj.bonusAmt = self.session['BonusOne']+self.session['BonusTwo']

		obj.put()
		self.response.out.write(json.dumps(({'blah': 'blah'}))) # ?


class AjaxMemoryHandler(webapp.RequestHandler):
	def get(self):
		que=db.Query(FinalJudgmentData)
		que.order("usernum").order("scenario").order("judgmentNumber")
		d=que.fetch(limit=10000)
		doRender(self, 'ajaxTest.htm',{'d':d})

	def post(self):
		self.session=get_current_session()

		# testOrder = 0: memory first
		# memOrder = 0: ask about outcomes given drug first

		# TO = 0, MO = 0: E|C, C|E, Causal
		# TO = 0, MO = 1: C|E, E|C, Causal
		# TO = 1, MO = 0: Causal, E|C, C|E
		# TO = 1, MO = 1: Causal, C|E, E|C

		if (int(self.session['testOrder']) == 0) & (int(self.session['memOrder']) == 0):
			judgmentOrder = 0 # E|C, C|E, Causal
		elif (int(self.session['testOrder']) == 0) & (int(self.session['memOrder']) == 1):
			judgmentOrder = 1 # C|E, E|C, Causal
		elif (int(self.session['testOrder']) == 1) & (int(self.session['memOrder']) == 0):
			judgmentOrder = 2 # Causal, E|C, C|E
		elif (int(self.session['testOrder']) == 1) & (int(self.session['memOrder']) == 1):
			judgmentOrder = 3 # Causal, C|E, E|C
		else:
			judgmentOrder = 100

  		usernum = self.session['usernum']
  		scenario = self.session['scenario']

  		valence = str(self.request.get('valence')) # this is the match between position2 and frequency2; sent to this handler as 'rare-positive' or 'rare-negative'
		condition = str(self.request.get('condition')) # story, monetary, or combined
  		leftDrugName = str(self.request.get('leftDrugName'))
  		rightDrugName = str(self.request.get('rightDrugName'))
  		leftDrugRarity = str(self.request.get('leftDrugRarity'))
  		rightDrugRarity = str(self.request.get('rightDrugRarity'))
		leftDrugColor = str(self.request.get('leftDrugColor'))
  		rightDrugColor = str(self.request.get('rightDrugColor'))
  		leftNumberBad = int(self.request.get('leftNumberBad'))
  		rightNumberBad = int(self.request.get('rightNumberBad'))
  		goodOutcomesLeft = int(self.request.get('goodOutcomesLeft'))
  		goodOutcomesRight = int(self.request.get('goodOutcomesRight'))
  		badOutcomesLeft = int(self.request.get('badOutcomesLeft'))
  		badOutcomesRight = int(self.request.get('badOutcomesRight'))

  		logging.info("usernum: " + str(usernum))
  		logging.info('account: ' + str(self.session['account']))
  		logging.info("valence: "+ str(valence))
		logging.info("condition: "+ str(condition))
  		logging.info("leftDrugName: "+ str(leftDrugName))
  		logging.info("rightDrugName: "+ str(rightDrugName))
  		logging.info("leftDrugRarity: "+ str(leftDrugRarity))
  		logging.info("rightDrugRarity: "+ str(rightDrugRarity))
		logging.info("leftDrugColor: "+ str(leftDrugColor))
  		logging.info("rightDrugColor: "+ str(rightDrugColor))
  		logging.info("leftNumberBad: "+ str(leftNumberBad))
  		logging.info("rightNumberBad: "+ str(rightNumberBad))
  		logging.info("goodOutcomesLeft: "+ str(goodOutcomesLeft))
  		logging.info("goodOutcomesRight: "+ str(goodOutcomesRight))
  		logging.info("badOutcomesLeft: "+ str(badOutcomesLeft))
  		logging.info("badOutcomesRight: "+ str(badOutcomesRight))
  		logging.info("memOrder: " + str(self.session['memOrder']))
  		logging.info("testOrder: " + str(self.session['testOrder']))
  		logging.info("judgmentOrder: "+ str(judgmentOrder))


  		judgmentOrder = judgmentOrder




		que = db.Query(FinalJudgmentData).filter('usernum =', self.session['usernum']).filter('scenario =', scenario)
		results = que.fetch(limit=1000)


		# make all of the data items into 3-value arrays, then make a loop to put them in the datastore
		if (len(results) == 0):
			logging.info('NEW ENTRY')
			newajaxmessage = FinalJudgmentData(
				# user properties
				user=self.session['userkey'],
				usernum = usernum,
				account = self.session['account'],
				# scenario properties
				scenario = scenario,
				valence = valence,
				condition = condition,
				# drug properties
				leftDrugName = leftDrugName,
				rightDrugName = rightDrugName,
				leftDrugRarity = leftDrugRarity, # DO THESE
				rightDrugRarity = rightDrugRarity,
				leftDrugColor = leftDrugColor,
				rightDrugColor = rightDrugColor,
				leftNumberBad = leftNumberBad,
				rightNumberBad = rightNumberBad,
				goodOutcomesLeft = goodOutcomesLeft,
				goodOutcomesRight = goodOutcomesRight,
				badOutcomesLeft = badOutcomesLeft,
				badOutcomesRight = badOutcomesRight,
				# causalJudgment = causalJudgment, Not this handler
				judgmentOrder = judgmentOrder);

			newajaxmessage.put()
			self.response.out.write(json.dumps(({'blah': 'blah'}))) # not sure what this does?

		else:
			logging.info('UPDATING CURRENT')
			obj = que.get()

			# user properties
			obj.user=self.session['userkey']
			obj.usernum = usernum
			obj.account = self.session['account']

			# scenario properties
			obj.scenario = scenario
			obj.condition = condition
			obj.valence = valence

			# drug properties
			obj.leftDrugName = leftDrugName
			obj.rightDrugName = rightDrugName
			obj.leftDrugRarity = leftDrugRarity # DO THESE
			obj.rightDrugRarity = rightDrugRarity
			obj.leftDrugColor = leftDrugColor
			obj.rightDrugColor = rightDrugColor
			obj.leftNumberBad = leftNumberBad
			obj.rightNumberBad = rightNumberBad
			obj.goodOutcomesLeft = goodOutcomesLeft
			obj.goodOutcomesRight = goodOutcomesRight
			obj.badOutcomesLeft = badOutcomesLeft
			obj.badOutcomesRight = badOutcomesRight
			# causalJudgment = causalJudgment, Not this handler
			obj.judgmentOrder = judgmentOrder

			obj.put()
			self.response.out.write(json.dumps(({'blah': 'blah'}))) # ?


class AjaxCausalHandler(webapp.RequestHandler):
	def get(self):
		# I don't even think I need this handler...
		que=db.Query(FinalJudgmentData)
		que.order("usernum").order("scenario").order("judgmentNumber")
		d=que.fetch(limit=10000)
		doRender(self, 'ajaxCausalTest.htm',{'d':d})

	def post(self):
		self.session=get_current_session()
		# message=str(self.request.get('message'))

		usernum = self.session['usernum']
		scenario = self.session['scenario']

		causalJudgment = int(self.request.get('judgmentInput'))


  		usernum = self.session['usernum']
  		scenario = self.session['scenario']

  		logging.info("usernum: " + str(usernum))
  		logging.info('account: ' + str(self.session['account']))
  		logging.info('scenario: '+str(scenario))



		# how to check if there are example rows in the datastore
		que = db.Query(FinalJudgmentData).filter('usernum =', self.session['usernum']).filter('scenario =', scenario)
		results = que.fetch(limit=1000)

		# make all of the data items into 3-value arrays, then make a loop to put them in the datastore
		if (len(results) == 0):
			logging.info('NEW ENTRY')
			newajaxmessage = FinalJudgmentData(
				# user properties
				user=self.session['userkey'],
				usernum = usernum,
				account = self.session['account'],
				# scenario properties
				scenario = scenario,
				# condition = self.session['conditions'][self.session['scenario']],
				# drug properties
				# leftDrugName = drugA_Name,
				# rightDrugName = drugB_Name,
				# leftDrugRarity = leftDrugRarity, # DO THESE
				# rightDrugRarity = rightDrugRarity,
				# leftDrugColor = leftDrugColor,
				# rightDrugColor = rightDrugColor,
				# leftNumberBad = leftNumberBad, Not this handler
				# rightNumberBad = rightNumberBad, Not this handler
				# goodOutcomesLeft = goodOutcomesLeft,
				# goodOutcomesRight = goodOutcomesRight,
				# badOutcomesLeft = badOutcomesLeft,
				# badOutcomesRight = badOutcomesRight,
				causalJudgment = causalJudgment);
				# judgmentOrder = judgmentOrder);

			newajaxmessage.put()
			self.response.out.write(json.dumps(({'blah': 'blah'}))) # not sure what this does?

		else:
			logging.info('UPDATING CURRENT')
			obj = que.get()

			# user properties
			obj.user=self.session['userkey']
			obj.usernum = usernum
			obj.account = self.session['account']
			# scenario properties
			obj.scenario = scenario
			# obj.condition = self.session['conditions'][self.session['scenario']]
			# drug properties
			# obj.leftDrugName = drugA_Name
			# obj.rightDrugName = drugB_Name
			# obj.leftDrugRarity = leftDrugRarity # DO THESE
			# obj.rightDrugRarity = rightDrugRarity
			# obj.leftDrugColor = leftDrugColor
			# obj.rightDrugColor = rightDrugColor
			# leftNumberBad = leftNumberBad, Not this handler
			# rightNumberBad = rightNumberBad, Not this handler
			# goodOutcomesLeft = goodOutcomesLeft,
			# goodOutcomesRight = goodOutcomesRight,
			# badOutcomesLeft = badOutcomesLeft,
			# badOutcomesRight = badOutcomesRight,
			obj.causalJudgment = causalJudgment
			# obj.judgmentOrder = judgmentOrder

			obj.put()
			self.response.out.write(json.dumps(({'blah': 'blah'}))) # ?


###############################################################################
############################## ScenarioHandler ################################
###############################################################################
# The main handler for all the "scenarios" (e.g., one patient)
class ScenarioHandler(webapp.RequestHandler):
	def get(self):
		self.session = get_current_session()
		logging.info("THIS IS A TEST")


		try:
			scenario = self.session['scenario']

			if scenario == 0:
				drugs = [self.session['drugNames'][0], self.session['drugNames'][1]]
				drugColors = [self.session['drugColors'][0], self.session['drugColors'][1]]

				obj = User.get(self.session['userkey']);
				obj.progress = 1
				obj.put()
			else:
				drugs = [self.session['drugNames'][2], self.session['drugNames'][3]]
				drugColors = [self.session['drugColors'][2], self.session['drugColors'][3]]


				obj = User.get(self.session['userkey']);
				obj.progress = 3
				obj.put()



			# position1 = self.session['position1']


			# if(valence == 'positive'):
			# 	data = self.session['posParadigmData']
			# 	group = self.session['posGroupData']
			# else:
			# 	data = self.session['negParadigmData']
			# 	group = self.session['negGroupData']

			group = self.session['v1_Data'][scenario]
			data = self.session['v2_Data'][scenario]


			doRender(self, 'scenario.htm',
				{'paradigmData':data,
				'groupData':group,
				'drugNames': self.session['drugNames'],
				'diseaseNames': self.session['diseaseNames'],
				'frequency1': self.session['frequency1'],
				'frequency2': self.session['frequency2'][scenario],
				'condition':condition, # monetary, story, combined
				'scenario': self.session['scenario'],
				'drugs': drugs,
				'drugColors': drugColors,
				'position1': self.session['position1'],
				'position2': self.session['position2'],
				'trialNumber': self.session['trialNumber'],
				'reloads': self.session['reloads']})


		except KeyError:
			doRender(self, 'mturkid.htm',
				{'error':1})


	def post(self):
		self.session = get_current_session()

		scenario = self.session['scenario']
		# scenario = 0 # testing




		if scenario == 0:
			drugs = [self.session['drugNames'][0], self.session['drugNames'][1]]
			drugColors = [self.session['drugColors'][0], self.session['drugColors'][1]]
		else:
			drugs = [self.session['drugNames'][2], self.session['drugNames'][3]]
			drugColors = [self.session['drugColors'][2], self.session['drugColors'][3]]

		position1 = self.session['position1']

		# self.session['testOrder'] = 1 # testing

		logging.info('TEST ORDER: '+str(self.session['testOrder']))



		doRender(self, 'mJudgment.htm',
			{'drugNames': self.session['drugNames'],
			'diseaseNames': self.session['diseaseNames'],
			'drugs': drugs,
			'drugColors': drugColors,
			'position1': position1,
			'testOrder':self.session['testOrder'],
			'frequency2':self.session['frequency2'][scenario],
			'position2': self.session['position2'],
			'memOrder':self.session['memOrder']})


class ProgressCheckHandler(webapp.RequestHandler):
	def get(self):
		self.session = get_current_session()

		logging.info('HANDLER IS HANDLING')
		o = User.get(self.session['userkey']);
		p = o.progress

		# p = 2
		if (p == 2) | (p == 4):
			p = 2

		logging.info('PROGRESS: '+str(p))

		# create json object to send back as "data"
		data = json.dumps(p)

		# self.response.headers['Content-Type'] = 'application/json; charset=UTF-8'
		self.response.out.write(data) # this is the function you need!


# first and second judgment refers to the get/post requests, NOT ajax
class FinalJudgmentHandler(webapp.RequestHandler):
	def get(self):
		# this one is only used when they load the scenario page but should be on the test page
		self.session = get_current_session()

		scenario = self.session['scenario']
		# scenario = 0 # testing



		if scenario == 0:
			drugs = [self.session['drugNames'][0], self.session['drugNames'][1]]
			drugColors = [self.session['drugColors'][0], self.session['drugColors'][1]]
		else:
			drugs = [self.session['drugNames'][2], self.session['drugNames'][3]]
			drugColors = [self.session['drugColors'][2], self.session['drugColors'][3]]

		position1 = self.session['position1']

		# self.session['testOrder'] = 1 # testing

		logging.info('TEST ORDER: '+str(self.session['testOrder']))


		doRender(self, 'mJudgment.htm',
			{'drugNames': self.session['drugNames'],
			'diseaseNames': self.session['diseaseNames'],
			'drugs': drugs,
			'drugColors': drugColors,
			'position1': position1,
			'testOrder':self.session['testOrder'],
			'frequency2':self.session['frequency2'][scenario],
			'position2': self.session['position2'],
			'memOrder':self.session['memOrder']})

	def post(self):

		self.session = get_current_session()



		self.session['scenario'] += 1
		# self.session['scenario'] = 1 # testing

		scenario=self.session['scenario']



		# does it make sense to have multiple scenarios? How long should our datasets be?
		if scenario<=NumScenarios-1: #have more scenarios to go
			obj = User.get(self.session['userkey']);
			obj.progress = 2
			obj.put()

			self.session['trialNumber'] = 0
			self.session['reloads']		= 0

			disease = self.session['diseaseNames'][1]
			drugs = [self.session['drugNames'][2], self.session['drugNames'][3]]

			# valence = self.session['frequency2'][scenario]

			position1 = self.session['position1']
			doRender(self, 'newscenario.htm',
				{'bonus':self.session['BonusOne'],
				'disease': disease,
				'drugs': drugs,
				'drugColors':self.session['drugColors'],
				'frequency2':self.session['frequency2'][scenario],
				'position1': position1})

		else:
			obj = User.get(self.session['userkey']);
			obj.progress = 4
			obj.put()
			doRender(self, 'demographics.htm')




###############################################################################
############################## Small Handlers #################################
###############################################################################

class TestHandler(webapp.RequestHandler):	# handler that renders a specific page, for testing purposes
	def get(self):
		usernum = 2 # testing
		logging.info('TEST HANDLER')
		self.session = get_current_session()

		# new data method for E1
		# Data1_var1 is the drug or shape1 in the first scenario: 0 is common, 1 is rare
		a = [[0]*36, [1]*12]
		a = [item for sublist in a for item in sublist]

		# Data1_var2 is the outcome/face or shape2: 0 is common, 1 is rare
		b = [[0]*24, [1]*12, [0]*8, [1]*4]
		b = [item for sublist in b for item in sublist]

		# random data order
		order = list(range(48))
		random.shuffle(order)

		# first scenario
		Data1_var1 = []
		Data1_var2 = []

		for i in order:
			Data1_var1.append(a[i])
			Data1_var2.append(b[i])

		random.shuffle(order)

		# second scenario
		Data2_var1 = []
		Data2_var2 = []

		for i in order:
			Data1_var1.append(a[i])
			Data1_var2.append(b[i])

		v1_Data = [Data1_var1, Data2_var1]
		v2_Data = [Data1_var2, Data2_var2]

		# randomize left/right for drug A/B at the level of the scenario
		# default is 0, A on the left. 1 is A on the right
		# old code: this is now position1, randomized below
		# position = []
		# for i in range(0, NumScenarios):
		# 	position.append(random.choice([0,1]))

		# order of asking (memory vs causal)
		testOrder = random.choice([0,1])

		# within memory, order of asking C|E or E|C
		# 0 is E|C first
		memOrder = random.choice([0,1])

		# testOrder = 0: memory first
		# memOrder = 0: ask about outcomes given drug first

		# TO = 0, MO = 0: E|C, C|E, Causal
		# TO = 0, MO = 1: C|E, E|C, Causal
		# TO = 1, MO = 0: Causal, E|C, C|E
		# TO = 1, MO = 1: Causal, C|E, E|C

		# 8 possible orders:
		t = round(time.time(),0)

		TO = (t % 6)+1 # between 1 and 6
		# TO = 1: Causal, E|C, C|E
		# TO = 2: Causal, C|E, E|C
		# TO = 3: E|C, Causal, C|E
		# TO = 4: E|C, C|E, Causal
		# TO = 5: C|E, Causal, E|C
		# TO = 6: C|E, E|C, Causal

		# note: E|C is "memory1", C|E is "memory2"


		# position1, position2, and frequency1 are counterbalanced at the participant level
			# doesn't make sense to do this by scenario; if the square is common in scenario 1, that has
			# nothing to do with whether the pentagon is common in scenario 2. Same with drug names/colors

		# position1: is var 1 (drug, shape1) reversed on the screen? (what would be left is now on right)
		# position2: is var 2 (face, shape2) reversed on the screen?
		# frequency1: is the common state on the left or right?
			# if 0, the shape/pill on the left is common. If 1, the shape/pill on the right is common.

		# frequency2: is the common state of var 2 (face, shape2) reversed?
			# THIS IS OUTCOME VALENCE, MANIPULATED WITHIN SUBJECTS

		# randomly determine position1/position2/frequency1
		t = round(time.time(), 0)

		if t % 8 == 1:
			position1 = 0
			position2 = 0
			frequency1 = 0
		elif t % 8 == 2:
			position1 = 0
			position2 = 0
			frequency1 = 1
		elif t % 8 == 3:
			position1 = 0
			position2 = 1
			frequency1 = 0
		elif t % 8 == 4:
			position1 = 0
			position2 = 1
			frequency1 = 1
		elif t % 8 == 5:
			position1 = 1
			position2 = 0
			frequency1 = 0
		elif t % 8 == 6:
			position1 = 1
			position2 = 0
			frequency1 = 1
		elif t % 8 == 7:
			position1 = 1
			position2 = 1
			frequency1 = 0
		elif t % 8 == 0:
			position1 = 1
			position2 = 1
			frequency1 = 1

		frequency2 = [0,1] # base rates of var2; for story/combined, 0 is rare-positive, 1 is rare-negative
		random.shuffle(frequency2) # conditions in random order

		# cover story counterbalance
		if usernum % 3 == 0:
			condition = 'combined'
		elif usernum % 3 == 1:
			condition = 'story'
		elif usernum % 3 == 2:
			condition = 'monetary'
		logging.info(condition)


		# shapes
		# shape names: 'SQUARE', 'CIRCLE', 'STAR', 'TRIANGLE', 'OVAL', 'DIAMOND', 'RECTANGLE', 'PENTAGON'
		# shapeNames = list(range(8))
		# random.shuffle(shapeNames) # which shapes they see when
		#
		shapeNames = [0,1,2,3]


		# disease names

		diseaseNames = ['Duastea', 'Stectosis']
		# random.shuffle(diseaseNames)

		# drug names
		# drugNames = ['XF702', 'BT339', 'GS596', 'PR242']
		drugNames = [0,1,2,3]
		# random.shuffle(drugNames)

		# drugColors = ['blue', 'green', 'orange', 'purple']
		drugColors = [0,1,2,3]
		# random.shuffle(drugColors)

		trialGuesses = [0]*LengthOfData

		# running tally of bonuses
		runningBonuses = [0,0]

		scenario = 0
		doRender(self, 'scenario.htm',
			{'v1_Data':v1_Data[scenario], # var1
			'v2_Data':v2_Data[scenario], # var2
			'drugNames': drugNames,
			'shapeNames': shapeNames,
			'disease': diseaseNames[0],
			'frequency1': 0,
			'frequency2': 0,
			'condition':condition, # monetary, story, combined
			'scenario': 0,
			'drugs': [drugNames[0], drugNames[1]],
			'drugColors': drugColors,
			'position1': 0,
			'position2': 0,
			'trialNumber': 0,
			'reloads': 0,
			'testOrder':TO, # CHANGE FROM PILOT: ask the three in any order.
			'rewardAmount':rewardAmount})


class InstructionsHandler(webapp.RequestHandler):
	def get(self):
		self.session = get_current_session()
		doRender(self, 'task.htm',
			{'position2':self.session['position2']})

class preScenarioHandler(webapp.RequestHandler):
	def get(self):
		self.session = get_current_session()
		disease = self.session['diseaseNames'][0]
		drugs = [self.session['drugNames'][0], self.session['drugNames'][1]]
		position1 = self.session['position1']
		valence = self.session['frequency2'][0]

		condition = self.session['condition'] # monetary, combined, story
		logging.info("PRESCENARIO HANDLER")
		doRender(self, 'prescenario.htm',
			{'disease':disease,
			'drugs': drugs,
			'shapes':[0,1,2,3],
			'valence':valence,
			'condition':condition,
			'drugColors':self.session['drugColors'],
			'position1':position1}) # don't need scenario, it's always 0

class DataHandler(webapp.RequestHandler):
	def get(self):

		doRender(self, 'datalogin.htm')


	def post(self):
		self.session = get_current_session()
		password=self.request.get('password')
		page = self.request.get('whichPage')


		if password == "gZ2BYJxfCY5SiyttS8zl":
		# if password == "": # testing

			que=db.Query(ScenarioData)
			que.order("usernum").order("scenario").order("trialNumber")
			d=que.fetch(limit=10000)

			que2=db.Query(User)
			que2.order("usernum")
			u=que2.fetch(limit=10000)

			que3 = db.Query(FinalJudgmentData)
			que3.order("usernum").order("scenario")
			t = que3.fetch(limit=10000)

			if page == 'scenario':
				doRender(
					self,
					'data.htm',
					{'d':d})

			elif page == 'user':
				doRender(
					self,
					'userData.htm',
					{'u':u})

			else:
				doRender(self, 'ajaxTest.htm',
					{'t':t})

			# elif page == 'causalTest':
			# 	doRender(self, 'ajaxCausalTest.htm',
			# 		{'c':c})
		else:
			doRender(self, 'dataloginfail.htm')




class QualifyHandler(webapp.RequestHandler):
	def get(self):
		doRender(self, 'qualify.htm')

class DNQHandler(webapp.RequestHandler):
	def get(self):
		doRender(self, 'do_not_qualify.htm')

##############################################################################
############################ DemographicsHandler #############################
##############################################################################
# This handler is a bit confusing - it has all this code to calculate the
# correct race number

class DemographicsHandler(webapp.RequestHandler):
	def get(self):
		doRender(self, 'demographics.htm')

	def post(self):
		self.session=get_current_session()
		bonus = self.session['BonusOne']+self.session['BonusTwo']
		try:


			sex=int(self.request.get('sex'))
			ethnicity=int(self.request.get('ethnicity'))
			racel=map(int,self.request.get_all('race')) #race list

			age=int(self.request.get('ageInput'))

			logging.info("race list")
			logging.info(racel)

			rl1=int(1 in racel)
			rl2=int(2 in racel)
			rl3=int(3 in racel)
			rl4=int(4 in racel)
			rl5=int(5 in racel)
			rl6=int(6 in racel)
			rl7=int(7 in racel)

	#Amer Indian, Asian, Native Hawaiian, Black, White, More than one, No Report
	#race_num is a number corresponding to a single race AmerInd (1) - White(5)
			race_num=rl1*1+rl2*2+rl3*3+rl4*4+rl5*5

			morethanonerace=0
			for i in [rl1,rl2,rl3,rl4,rl5]:
					if i==1:
							morethanonerace+=1
			if rl6==1:
					morethanonerace+=2

			if rl7==1:  #dont want to report
					race=7
			elif morethanonerace>1:
					race=6
			elif morethanonerace==1:
					race=race_num

			logging.info("race")
			logging.info(race)



			Completion_Code=random.randint(10000000,99999999)


			obj = User.get(self.session['userkey']);
			# obj.Completion_Code = Completion_Code
			obj.sex = sex
			obj.ethnicity = ethnicity
			obj.race = race
			obj.age = age
			obj.put();


			# self.session.__delitem__('usernum')
			# self.session.__delitem__('username')
			# self.session.__delitem__('userkey')
			# self.session.__delitem__('scenario')
			# self.session.__delitem__('datalist')

			self.session.__delitem__('account')
			# self.session.__delitem__('BonusOne')
			# self.session.__delitem__('BonusTwo')
			self.session.__delitem__('condition')
			self.session.__delitem__('frequency2')
			self.session.__delitem__('diseaseNames')
			self.session.__delitem__('drugColors')
			self.session.__delitem__('drugNames')
			self.session.__delitem__('position2')
			self.session.__delitem__('negGroupData')
			self.session.__delitem__('negParadigmData')
			self.session.__delitem__('posGroupData')
			self.session.__delitem__('posParadigmData')
			self.session.__delitem__('position1')
			self.session.__delitem__('runningBonuses')
			self.session.__delitem__('scenario')
			self.session.__delitem__('testOrder')
			self.session.__delitem__('trialGuesses')
			self.session.__delitem__('userkey')
			self.session.__delitem__('usernum')



			doRender(self, 'logout.htm',
				{'bonus':bonus})
		except:
			doRender(self, 'logout.htm',
				{'bonus':bonus})


###############################################################################
############################### MturkIDHandler ################################
###############################################################################

class MturkIDHandler(webapp.RequestHandler):
	def get(self):
		doRender(self, 'mturkid.htm',
			{'error':0})

	def post(self):

		usernum = create_or_increment_NumOfUsers()

		browser = self.request.get('browser')
		ID = self.request.get('ID')
		account = ID
		logging.info('BROWSER: '+browser)


		# make sure they qualify

		form_fields = {
			"ID": ID,
			"ClassOfStudies": 'Cory Dissertation',
			"StudyNumber": 1
			}

		form_data = urllib.urlencode(form_fields)
		url="http://www.mturk-qualify.appspot.com"
		result = urlfetch.fetch(url=url,
								payload=form_data,
								method=urlfetch.POST,
								headers={'Content-Type': 'application/x-www-form-urlencoded'})

		if result.content=="0":
			#self.response.out.write("ID is in global database.")
			doRender(self, 'do_not_qualify.htm')

		elif result.content=="1":
			# Check if the user already exists
			que = db.Query(User).filter('account =',ID)
			results = que.fetch(limit=1)

			if (len(results) > 0) & (ID!='ben'):
				doRender(self, 'do_not_qualify.htm')

			# If user is qualified (http://www.mturk-qualify.appspot.com returns 1)
			else:
				#Create the User object and log the user in.
				usernum = create_or_increment_NumOfUsers()

				browser = self.request.get('browser')
				# logging.info('BROWSER: '+browser)
				#Make the data that this subject will see.

				#It is made once and stored both in self.session and in database

				# new data method for E1
				# Data1_var1 is the drug or shape1 in the first scenario: 0 is common, 1 is rare
				a = [[0]*36, [1]*12]
				a = [item for sublist in a for item in sublist]

				# Data1_var2 is the outcome/face or shape2: 0 is common, 1 is rare
				b = [[0]*24, [1]*12, [0]*8, [1]*4]
				b = [item for sublist in b for item in sublist]

				# random data order
				order = list(range[48])
				random.shuffle(order)

				# first scenario
				Data1_var1 = []
				Data1_var2 = []

				for i in order:
					Data1_var1.append(a[i])
					Data1_var2.append(b[i])

				random.shuffle(order)

				# second scenario
				Data2_var1 = []
				Data2_var2 = []

				for i in order:
					Data1_var1.append(a[i])
					Data1_var2.append(b[i])

				v1_Data = [Data1_var1, Data2_var1]
				v2_Data = [Data1_var2, Data2_var2]

				# randomize left/right for drug A/B at the level of the scenario
				# default is 0, A on the left. 1 is A on the right
				# old code: this is now position1, randomized below
				# position = []
				# for i in range(0, NumScenarios):
				# 	position.append(random.choice([0,1]))

				# order of asking (memory vs causal)
				testOrder = random.choice([0,1])

				# within memory, order of asking C|E or E|C
				# 0 is E|C first
				memOrder = random.choice([0,1])

				# testOrder = 0: memory first
				# memOrder = 0: ask about outcomes given drug first

				# TO = 0, MO = 0: E|C, C|E, Causal
				# TO = 0, MO = 1: C|E, E|C, Causal
				# TO = 1, MO = 0: Causal, E|C, C|E
				# TO = 1, MO = 1: Causal, C|E, E|C

				# position1, position2, and frequency1 are counterbalanced at the participant level
					# doesn't make sense to do this by scenario; if the square is common in scenario 1, that has
					# nothing to do with whether the pentagon is common in scenario 2. Same with drug names/colors

				# position1: is var 1 (drug, shape1) reversed on the screen? (what would be left is now on right)
				# position2: is var 2 (face, shape2) reversed on the screen?
				# frequency1: is the common state on the left or right?
					# if 0, the shape/pill on the left is common. If 1, the shape/pill on the right is common.

				# frequency2: is the common state of var 2 (face, shape2) reversed?
					# THIS IS OUTCOME VALENCE, MANIPULATED WITHIN SUBJECTS

				# randomly determine position1/position2/frequency1
				t = round(time.time(), 0)

				if usernum % 8 == 1:
					position1 = 0
					position2 = 0
					frequency1 = 0
				elif usernum % 8 == 2:
					position1 = 0
					position2 = 0
					frequency1 = 1
				elif usernum % 8 == 3:
					position1 = 0
					position2 = 1
					frequency1 = 0
				elif usernum % 8 == 4:
					position1 = 0
					position2 = 1
					frequency1 = 1
				elif usernum % 8 == 5:
					position1 = 1
					position2 = 0
					frequency1 = 0
				elif usernum % 8 == 6:
					position1 = 1
					position2 = 0
					frequency1 = 1
				elif usernum % 8 == 7:
					position1 = 1
					position2 = 1
					frequency1 = 0
				elif usernum % 8 == 0:
					position1 = 1
					position2 = 1
					frequency1 = 1

				frequency2 = [0,1] # base rates of var2; for story/combined, 0 is rare-positive, 1 is rare-negative
				random.shuffle(frequency2) # conditions in random order

				# cover story counterbalance
				if usernum % 3 == 0:
					condition = 'combined'
				elif usernum % 3 == 1:
					condition = 'story'
				elif usernum % 3 == 2:
					condition = 'monetary'

				if condition == 'monetary':
					# shapes
					# shape names: 'SQUARE', 'CIRCLE', 'STAR', 'TRIANGLE', 'OVAL', 'DIAMOND', 'RECTANGLE', 'PENTAGON'
					shapeNames = list(range(8))
					random.shuffle(shapeNames) # which shapes they see when

				else:

					# disease names

					diseaseNames = ['Duastea', 'Stectosis']
					random.shuffle(diseaseNames)

					# drug names
					# drugNames = ['XF702', 'BT339', 'GS596', 'PR242']
					drugNames = [0,1,2,3]
					random.shuffle(drugNames)

					# drugColors = ['blue', 'green', 'orange', 'purple']
					drugColors = [0,1,2,3]
					random.shuffle(drugColors)

				trialGuesses = [0]*LengthOfData

				# running tally of bonuses
				runningBonuses = [0,0]

				newuser = User(
					usernum=usernum,
					account=account,
					browser=browser,
					sex=0,
					ethnicity=0,
					race=0,
					age=0,
					bonusAmt=0,
					testOrder = testOrder,
					memOrder = memOrder,
					progress = 0);

				# dataframe modeling, but I'm not sure what exactly
				userkey = newuser.put()

				# this stores the new user in the datastore
				newuser.put()

				# store these variables in the session
				self.session=get_current_session() #initialize sessions

				self.session['account']				= account
				self.session['BonusOne']			= 0
				self.session['BonusTwo']			= 0
				self.session['frequency1']			= frequency1
				self.session['frequency2']			= frequency2 # this is an array, ex: [0,1]
				self.session['diseaseNames']		= diseaseNames
				self.session['drugColors']			= drugColors
				self.session['drugNames']			= drugNames
				self.session['position1']			= position1
				self.session['position2']			= position2
				self.session['v1_Data']				= v1_Data
				self.session['v2_Data']				= v2_Data
				self.session['shapeNames']			= shapeNames

				# self.session['negGroupData']		= negGroupData
				# self.session['negParadigmData']		= negParadigmData
				# self.session['posGroupData']		= posGroupData
				# self.session['posParadigmData']		= posParadigmData
				self.session['runningBonuses']		= runningBonuses
				self.session['scenario']			= 0
				self.session['testOrder']			= testOrder
				self.session['trialGuesses']		= trialGuesses
				self.session['userkey']				= userkey
				self.session['usernum']				= usernum
				self.session['memOrder']			= memOrder
				self.session['trialNumber']			= 0
				self.session['reloads']				= 0


				doRender(self, 'qualify.htm')



		# If got no response back from http://www.mturk-qualify.appspot.com
		else:
		  error="The server is going slowly. Please reload and try again."
		  self.response.out.write(result.content)


###############################################################################
############################### MainAppLoop ###################################
###############################################################################

application = webapp.WSGIApplication([
	('/ajax', AjaxHandler),
	# ('/AjaxOutcomeMemoryTest', AjaxOutcomeMemoryHandler),
	('/AjaxMemoryTest', AjaxMemoryHandler),
	('/AjaxCausalTest', AjaxCausalHandler),
	('/preScenario', preScenarioHandler),
	('/instructions', InstructionsHandler),
	('/data', DataHandler),
	('/do_not_qualify', DNQHandler),
	('/scenario', ScenarioHandler),
	('/finalJudgment', FinalJudgmentHandler),
	('/qualify', QualifyHandler),
	('/progressCheck', ProgressCheckHandler),
	('/demographics', DemographicsHandler),
	('/mturkid', MturkIDHandler),
	# ('/.*',      MturkIDHandler)],  #default page
	('/.*',      TestHandler)],  # testing
	debug=True)

def main():
		run_wsgi_app(application)

if __name__ == '__main__':
	main()
