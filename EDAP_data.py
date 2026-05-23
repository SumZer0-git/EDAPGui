"""
Static data.

For easy reference any variable should be prefixed with the name of the file it
was either in originally, or where the primary code utilising it is.

Note: Some of this file comes from EDMarketConnector's edmc_data.py file
(https://github.com/EDCD/EDMarketConnector/blob/main/edmc_data.py).

"""

# Status.json / Dashboard Flags constants
FlagsDocked = 1 << 0             # on a landing pad in space or planet
FlagsLanded = 1 << 1             # on planet surface (not planet landing pad)
FlagsLandingGearDown = 1 << 2
FlagsShieldsUp = 1 << 3
FlagsSupercruise = 1 << 4         # While in super-cruise
FlagsFlightAssistOff = 1 << 5
FlagsHardpointsDeployed = 1 << 6
FlagsInWing = 1 << 7
FlagsLightsOn = 1 << 8
FlagsCargoScoopDeployed = 1 << 9
FlagsSilentRunning = 1 << 10
FlagsScoopingFuel = 1 << 11
FlagsSrvHandbrake = 1 << 12
FlagsSrvTurret = 1 << 13         # using turret view
FlagsSrvUnderShip = 1 << 14      # turret retracted
FlagsSrvDriveAssist = 1 << 15
FlagsFsdMassLocked = 1 << 16
FlagsFsdCharging = 1 << 17       # While charging and jumping for super-cruise or system jump
FlagsFsdCooldown = 1 << 18       # Following super-cruise or jump
FlagsLowFuel = 1 << 19           # < 25%
FlagsOverHeating = 1 << 20       # > 100%, or is this 80% now ?
FlagsHasLatLong = 1 << 21        # On when altimeter is visible (either OC/DRP mode or 2Km/SURF mode).
FlagsIsInDanger = 1 << 22
FlagsBeingInterdicted = 1 << 23
FlagsInMainShip = 1 << 24
FlagsInFighter = 1 << 25
FlagsInSRV = 1 << 26
FlagsAnalysisMode = 1 << 27      # Hud in Analysis mode
FlagsNightVision = 1 << 28
FlagsAverageAltitude = 1 << 29   # Alt from Average radius. On if alt shows OC/DRP, Off if alt not shown or showing 2Km/SURF.
FlagsFsdJump = 1 << 30           # While jumping to super-cruise or system jump. See also Flags2FsdHyperdriveCharging.
FlagsSrvHighBeam = 1 << 31

# Status.json / Dashboard Flags2 constants
Flags2OnFoot = 1 << 0
Flags2InTaxi = 1 << 1  # (or drop-ship/shuttle)
Flags2InMulticrew = 1 << 2  # (ie in someone else’s ship)
Flags2OnFootInStation = 1 << 3
Flags2OnFootOnPlanet = 1 << 4
Flags2AimDownSight = 1 << 5
Flags2LowOxygen = 1 << 6
Flags2LowHealth = 1 << 7
Flags2Cold = 1 << 8
Flags2Hot = 1 << 9
Flags2VeryCold = 1 << 10
Flags2VeryHot = 1 << 11
Flags2GlideMode = 1 << 12
Flags2OnFootInHangar = 1 << 13
Flags2OnFootSocialSpace = 1 << 14
Flags2OnFootExterior = 1 << 15
Flags2BreathableAtmosphere = 1 << 16
Flags2TelepresenceMulticrew = 1 << 17
Flags2PhysicalMulticrew = 1 << 18
Flags2FsdHyperdriveCharging = 1 << 19       # While charging and jumping for system jump
Flags2FsdScoActive = 1 << 20
Flags2Future21 = 1 << 21   # Probably Supercruise Assist on. To be confirmed.
Flags2Future22 = 1 << 22
Flags2Future23 = 1 << 23
Flags2Future24 = 1 << 24
Flags2Future25 = 1 << 25
Flags2Future26 = 1 << 26
Flags2Future27 = 1 << 27
Flags2Future28 = 1 << 28
Flags2Future29 = 1 << 29
Flags2Future30 = 1 << 30
Flags2Future31 = 1 << 31

# Status.json Dashboard GuiFocus constants
GuiFocusNoFocus = 0              # ship view
GuiFocusInternalPanel = 1        # right hand side
GuiFocusExternalPanel = 2        # left hand (nav) panel
GuiFocusCommsPanel = 3		     # top
GuiFocusRolePanel = 4		     # bottom
GuiFocusStationServices = 5
GuiFocusGalaxyMap = 6
GuiFocusSystemMap = 7
GuiFocusOrrery = 8
GuiFocusFSS = 9
GuiFocusSAA = 10
GuiFocusCodex = 11

# Journal.log Ship Name constants
ship_name_map = {
    'adder':                        'Adder',
    'anaconda':                     'Anaconda',
    'asp':                          'Asp Explorer',
    'asp_scout':                    'Asp Scout',
    'belugaliner':                  'Beluga Liner',
    'cobramkiii':                   'Cobra Mk III',
    'cobramkiv':                    'Cobra Mk IV',
    'cobramkv':                     'Cobra Mk V',
    'corsair':                      'Corsair',
    'clipper':                      'Panther Clipper',
    'cutter':                       'Imperial Cutter',
    'diamondback':                  'Diamondback Scout',
    'diamondbackxl':                'Diamondback Explorer',
    'dolphin':                      'Dolphin',
    'eagle':                        'Eagle',
    'empire_courier':               'Imperial Courier',
    'empire_eagle':                 'Imperial Eagle',
    'empire_fighter':               'Imperial Fighter',
    'empire_trader':                'Imperial Clipper',
    'explorer_nx':                  'Caspian Explorer',
    'federation_corvette':          'Federal Corvette',
    'federation_dropship':          'Federal Dropship',
    'federation_dropship_mkii':     'Federal Assault Ship',
    'federation_gunship':           'Federal Gunship',
    'federation_fighter':           'F63 Condor',
    'ferdelance':                   'Fer-de-Lance',
    'hauler':                       'Hauler',
    'independant_trader':           'Keelback',
    'independent_fighter':          'Taipan Fighter',
    'krait_mkii':                   'Krait Mk II',
    'krait_light':                  'Krait Phantom',
    'lakonminer':                   'Type-11 Prospector',
    'mamba':                        'Mamba',
    'mandalay':                     'Mandalay',
    'mediumtransport01':            'Lynx Highliner',
    'orca':                         'Orca',
    'panthermkii':                  'Panther Clipper Mk II',
    'python':                       'Python',
    'python_nx':                    'Python Mk II',
    'scout':                        'Taipan Fighter',
    'sidewinder':                   'Sidewinder',
    'smallcombat01_nx':             'Kestrel Mk II',
    'testbuggy':                    'Scarab',
    'type6':                        'Type-6 Transporter',
    'type7':                        'Type-7 Transporter',
    'type8':                        'Type-8 Transporter',
    'type9':                        'Type-9 Heavy',
    'type9_military':               'Type-10 Defender',
    'typex':                        'Alliance Chieftain',
    'typex_2':                      'Alliance Crusader',
    'typex_3':                      'Alliance Challenger',
    'viper':                        'Viper Mk III',
    'viper_mkiv':                   'Viper Mk IV',
    'vulture':                      'Vulture',
}

# Journal.log Ship Name to size constants
ship_size_map = {
    'adder':                         'S',
    'anaconda':                      'L',
    'asp':                           'M',
    'asp_scout':                     'M',
    'belugaliner':                   'L',
    'cobramkiii':                    'S',
    'cobramkiv':                     'S',
    'cobramkv':                      'S',
    'corsair':                       'M',
    'clipper':                       '',
    'cutter':                        'L',
    'diamondback':                   'S',
    'diamondbackxl':                 'S',
    'dolphin':                       'S',
    'eagle':                         'S',
    'empire_courier':                'S',
    'empire_eagle':                  'S',
    'empire_fighter':                '',
    'empire_trader':                 'L',
    'explorer_nx':                   'L',
    'federation_corvette':           'L',
    'federation_dropship':           'M',
    'federation_dropship_mkii':      'M',
    'federation_gunship':            'M',
    'federation_fighter':            '',
    'ferdelance':                    'M',
    'hauler':                        'S',
    'independant_trader':            'M',
    'independent_fighter':           '',
    'krait_mkii':                    'M',
    'krait_light':                   'M',
    'lakonminer':                    'M',
    'mamba':                         'M',
    'mandalay':                      'M',
    'mediumtransport01':             'M',
    'orca':                          'L',
    'panthermkii':                   'L',
    'python':                        'M',
    'python_nx':                     'M',
    'scout':                         '',
    'sidewinder':                    'S',
    'smallcombat01_nx':              'S',
    'testbuggy':                     '',
    'type6':                         'M',
    'type7':                         'L',
    'type8':                         'L',
    'type9':                         'L',
    'type9_military':                'L',
    'typex':                         'M',
    'typex_2':                       'M',
    'typex_3':                       'M',
    'viper':                         'S',
    'viper_mkiv':                    'S',
    'vulture':                       'S',
}

# Ship default RPY rates in deg/sec at 50% Supercruise throttle
# Default data comes from 'marx': https://forums.frontier.co.uk/threads/supercruise-handling-of-ships.396845/
ship_rpy_sc_50 = {
    'adder':                        {'RollRate': 90.0,  'PitchRate': 30.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'anaconda':                     {'RollRate': 40.0,  'PitchRate': 14.0,  'YawRate': 6.0,   'SunPitchUp+Time': 0.0},
    'asp':                          {'RollRate': 90.0,  'PitchRate': 30.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'asp_scout':                    {'RollRate': 120.0, 'PitchRate': 36.0,  'YawRate': 15.0,  'SunPitchUp+Time': 0.0},
    'belugaliner':                  {'RollRate': 60.0,  'PitchRate': 19.0,  'YawRate': 17.0,  'SunPitchUp+Time': 0.0},
    'cobramkiii':                   {'RollRate': 90.0,  'PitchRate': 36.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'cobramkiv':                    {'RollRate': 90.0,  'PitchRate': 24.0,  'YawRate': 10.0,  'SunPitchUp+Time': 0.0},
    'cobramkv':                     {'RollRate': 110.0, 'PitchRate': 37.0,  'YawRate': 22.0,  'SunPitchUp+Time': -0.25},
    'corsair':                      {'RollRate': 80.0,  'PitchRate': 21.0,  'YawRate': 10.0,  'SunPitchUp+Time': 0.0},
    'cutter':                       {'RollRate': 45.0,  'PitchRate': 14.0,  'YawRate': 8.0,   'SunPitchUp+Time': 1.0},
    'diamondback':                  {'RollRate': 90.0,  'PitchRate': 36.0,  'YawRate': 15.0,  'SunPitchUp+Time': 0.0},
    'diamondbackxl':                {'RollRate': 90.0,  'PitchRate': 26.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'dolphin':                      {'RollRate': 90.0,  'PitchRate': 28.0,  'YawRate': 19.0,  'SunPitchUp+Time': 0.0},
    'eagle':                        {'RollRate': 120.0, 'PitchRate': 33.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'empire_courier':               {'RollRate': 90.0,  'PitchRate': 30.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'empire_eagle':                 {'RollRate': 90.0,  'PitchRate': 30.0,  'YawRate': 15.0,  'SunPitchUp+Time': 0.0},
    'empire_trader':                {'RollRate': 72.0,  'PitchRate': 28.0,  'YawRate': 18.0,  'SunPitchUp+Time': 0.0},
    'explorer_nx':                  {'RollRate': 90.0,  'PitchRate': 28.0,  'YawRate': 18.0,  'SunPitchUp+Time': 0.0},
    'federation_corvette':          {'RollRate': 72.0,  'PitchRate': 21.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'federation_dropship':          {'RollRate': 72.0,  'PitchRate': 20.0,  'YawRate': 14.0,  'SunPitchUp+Time': 0.0},
    'federation_dropship_mkii':     {'RollRate': 90.0,  'PitchRate': 30.0,  'YawRate': 18.0,  'SunPitchUp+Time': 0.0},
    'federation_gunship':           {'RollRate': 60.0,  'PitchRate': 19.0,  'YawRate': 18.0,  'SunPitchUp+Time': 0.0},
    'ferdelance':                   {'RollRate': 72.0,  'PitchRate': 20.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'hauler':                       {'RollRate': 90.0,  'PitchRate': 33.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'independant_trader':           {'RollRate': 90.0,  'PitchRate': 26.0,  'YawRate': 11.0,  'SunPitchUp+Time': 0.0},
    'krait_mkii':                   {'RollRate': 90.0,  'PitchRate': 23.0,  'YawRate': 10.0,  'SunPitchUp+Time': 0.0},
    'krait_light':                  {'RollRate': 90.0,  'PitchRate': 23.0,  'YawRate': 10.0,  'SunPitchUp+Time': 0.0},
    'lakonminer':                   {'RollRate': 60.0,  'PitchRate': 18.0,  'YawRate': 18.0,  'SunPitchUp+Time': 0.0},
    'mamba':                        {'RollRate': 72.0,  'PitchRate': 20.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'mandalay':                     {'RollRate': 120.0, 'PitchRate': 40.0,  'YawRate': 24.0,  'SunPitchUp+Time': -1.0},
    'mediumtransport01':            {'RollRate': 120.0, 'PitchRate': 40.0,  'YawRate': 24.0,  'SunPitchUp+Time': 0.0},
    'orca':                         {'RollRate': 60.0,  'PitchRate': 20.0,  'YawRate': 18.0,  'SunPitchUp+Time': 0.0},
    'panthermkii':                  {'RollRate': 25.0,  'PitchRate': 16.0,  'YawRate': 10.0,  'SunPitchUp+Time': 1.0},
    'python':                       {'RollRate': 90.0,  'PitchRate': 23.0,  'YawRate': 10.0,  'SunPitchUp+Time': 0.0},
    'python_nx':                    {'RollRate': 90.0,  'PitchRate': 22.0,  'YawRate': 10.0,  'SunPitchUp+Time': 0.0},
    'sidewinder':                   {'RollRate': 120.0, 'PitchRate': 40.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'smallcombat01_nx':             {'RollRate': 120.0, 'PitchRate': 40.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'type6':                        {'RollRate': 90.0,  'PitchRate': 26.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'type7':                        {'RollRate': 60.0,  'PitchRate': 17.0,  'YawRate': 18.0,  'SunPitchUp+Time': 0.0},
    'type8':                        {'RollRate': 60.0,  'PitchRate': 16.0,  'YawRate': 9.0,   'SunPitchUp+Time': 0.0},
    'type9':                        {'RollRate': 18.0,  'PitchRate': 12.0,  'YawRate': 6.0,   'SunPitchUp+Time': 1.0},
    'type9_military':               {'RollRate': 17.0,  'PitchRate': 12.0,  'YawRate': 5.0,   'SunPitchUp+Time': 0.0},
    'typex':                        {'RollRate': 72.0,  'PitchRate': 20.0,  'YawRate': 14.0,  'SunPitchUp+Time': 0.0},
    'typex_2':                      {'RollRate': 72.0,  'PitchRate': 20.0,  'YawRate': 13.0,  'SunPitchUp+Time': 0.0},
    'typex_3':                      {'RollRate': 72.0,  'PitchRate': 20.0,  'YawRate': 14.0,  'SunPitchUp+Time': 0.0},
    'viper':                        {'RollRate': 90.0,  'PitchRate': 30.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'viper_mkiv':                   {'RollRate': 90.0,  'PitchRate': 26.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'vulture':                      {'RollRate': 90.0,  'PitchRate': 33.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0}
}

# Ship default RPY rates in deg/sec at 100% Supercruise throttle
# Default data comes from 'marx': https://forums.frontier.co.uk/threads/supercruise-handling-of-ships.396845/
ship_rpy_sc_100 = {
    'adder':                        {'RollRate': 90.0,  'PitchRate': 23.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'anaconda':                     {'RollRate': 36.0,  'PitchRate': 9.0,   'YawRate': 3.0,   'SunPitchUp+Time': 0.0},
    'asp':                          {'RollRate': 72.0,  'PitchRate': 23.0,  'YawRate': 5.0,   'SunPitchUp+Time': 0.0},
    'asp_scout':                    {'RollRate': 90.0,  'PitchRate': 28.0,  'YawRate': 10.0,  'SunPitchUp+Time': 0.0},
    'belugaliner':                  {'RollRate': 45.0,  'PitchRate': 13.0,  'YawRate': 15.0,  'SunPitchUp+Time': 0.0},
    'cobramkiii':                   {'RollRate': 72.0,  'PitchRate': 26.0,  'YawRate': 5.0,   'SunPitchUp+Time': 0.0},
    'cobramkiv':                    {'RollRate': 90.0,  'PitchRate': 16.0,  'YawRate': 7.0,   'SunPitchUp+Time': 0.0},
    'cobramkv':                     {'RollRate': 110.0, 'PitchRate': 37.0,  'YawRate': 22.0,  'SunPitchUp+Time': -0.25},
    'corsair':                      {'RollRate': 80.0,  'PitchRate': 21.0,  'YawRate': 10.0,  'SunPitchUp+Time': 0.0},
    'cutter':                       {'RollRate': 40.0,  'PitchRate': 9.0,   'YawRate': 5.0,   'SunPitchUp+Time': 1.0},
    'diamondback':                  {'RollRate': 90.0,  'PitchRate': 23.0,  'YawRate': 9.0,   'SunPitchUp+Time': 0.0},
    'diamondbackxl':                {'RollRate': 72.0,  'PitchRate': 20.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'dolphin':                      {'RollRate': 72.0,  'PitchRate': 19.0,  'YawRate': 13.0,  'SunPitchUp+Time': 0.0},
    'eagle':                        {'RollRate': 90.0,  'PitchRate': 24.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'empire_courier':               {'RollRate': 90.0,  'PitchRate': 24.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'empire_eagle':                 {'RollRate': 72.0,  'PitchRate': 23.0,  'YawRate': 9.0,   'SunPitchUp+Time': 0.0},
    'empire_trader':                {'RollRate': 72.0,  'PitchRate': 21.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'explorer_nx':                  {'RollRate': 73.0,  'PitchRate': 17.0,  'YawRate': 11.0,  'SunPitchUp+Time': 0.0},
    'federation_corvette':          {'RollRate': 60.0,  'PitchRate': 13.0,  'YawRate': 5.0,   'SunPitchUp+Time': 0.0},
    'federation_dropship':          {'RollRate': 72.0,  'PitchRate': 12.0,  'YawRate': 9.0,   'SunPitchUp+Time': 0.0},
    'federation_dropship_mkii':     {'RollRate': 72.0,  'PitchRate': 21.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'federation_gunship':           {'RollRate': 72.0,  'PitchRate': 12.0,  'YawRate': 11.0,  'SunPitchUp+Time': 0.0},
    'ferdelance':                   {'RollRate': 60.0,  'PitchRate': 12.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'hauler':                       {'RollRate': 90.0,  'PitchRate': 23.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'independant_trader':           {'RollRate': 90.0,  'PitchRate': 16.0,  'YawRate': 7.0,   'SunPitchUp+Time': 0.0},
    'krait_mkii':                   {'RollRate': 72.0,  'PitchRate': 13.0,  'YawRate': 6.0,   'SunPitchUp+Time': 0.0},
    'krait_light':                  {'RollRate': 72.0,  'PitchRate': 14.0,  'YawRate': 6.0,   'SunPitchUp+Time': 0.0},
    'lakonminer':                   {'RollRate': 48.0,  'PitchRate': 10.9,  'YawRate': 10.9,  'SunPitchUp+Time': 0.0},
    'mamba':                        {'RollRate': 72.0,  'PitchRate': 13.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'mandalay':                     {'RollRate': 90.0,  'PitchRate': 24.0,  'YawRate': 16.0,  'SunPitchUp+Time': -1.0},
    'mediumtransport01':            {'RollRate': 90.0,  'PitchRate': 24.0,  'YawRate': 16.0,  'SunPitchUp+Time': 0.0},
    'orca':                         {'RollRate': 51.0,  'PitchRate': 14.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'panthermkii':                  {'RollRate': 20.0,  'PitchRate': 9.7,   'YawRate': 6.0,   'SunPitchUp+Time': 1.0},
    'python':                       {'RollRate': 72.0,  'PitchRate': 14.0,  'YawRate': 6.0,   'SunPitchUp+Time': 0.0},
    'python_nx':                    {'RollRate': 90.0,  'PitchRate': 22.0,  'YawRate': 10.0,  'SunPitchUp+Time': 0.0},
    'sidewinder':                   {'RollRate': 90.0,  'PitchRate': 28.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'smallcombat01_nx':             {'RollRate': 90.0,  'PitchRate': 28.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'type6':                        {'RollRate': 72.0,  'PitchRate': 16.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'type7':                        {'RollRate': 45.0,  'PitchRate': 11.0,  'YawRate': 11.0,  'SunPitchUp+Time': 0.0},
    'type8':                        {'RollRate': 60.0,  'PitchRate': 16.0,  'YawRate': 9.0,   'SunPitchUp+Time': 0.0},
    'type9':                        {'RollRate': 15.0,  'PitchRate': 7.0,   'YawRate': 3.0,   'SunPitchUp+Time': 1.0},
    'type9_military':               {'RollRate': 15.0,  'PitchRate': 8.0,   'YawRate': 4.0,   'SunPitchUp+Time': 0.0},
    'typex':                        {'RollRate': 60.0,  'PitchRate': 13.0,  'YawRate': 9.0,   'SunPitchUp+Time': 0.0},
    'typex_2':                      {'RollRate': 72.0,  'PitchRate': 13.0,  'YawRate': 9.0,   'SunPitchUp+Time': 0.0},
    'typex_3':                      {'RollRate': 60.0,  'PitchRate': 12.0,  'YawRate': 9.0,   'SunPitchUp+Time': 0.0},
    'viper':                        {'RollRate': 72.0,  'PitchRate': 20.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'viper_mkiv':                   {'RollRate': 72.0,  'PitchRate': 16.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'vulture':                      {'RollRate': 72.0,  'PitchRate': 24.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0}
}

commodities = {
    "Chemicals": [
        "Agronomic Treatment", "Explosives", "Hydrogen Fuel", "Hydrogen Peroxide", "Liquid Oxygen",
        "Mineral Oil", "Nerve Agents", "Pesticides", "Rockforth Fertiliser", "Surface Stabilisers",
        "Synthetic Reagents", "Tritium", "Water"
    ],
    "Consumer Items": [
        "Clothing", "Consumer Technology", "Domestic Appliances", "Evacuation Shelter", "Survival Equipment"
    ],
    "Foods": [
        "Algae", "Animal Meat", "Coffee", "Fish", "Food Cartridges", "Fruit and Vegetables",
        "Grain", "Synthetic Meat", "Tea"
    ],
    "Industrial Materials": [
        "Ceramic Composites", "CMM Composite", "Insulating Membrane", "Meta-Alloys",
        "Micro-Weave Cooling Hoses", "Neofabric Insulation", "Polymers", "Semiconductors", "Superconductors"
    ],
    "Legal Drugs": [
        "Beer", "Bootleg Liquor", "Liquor", "Narcotics", "Onionhead Gamma Strain", "Tobacco", "Wine"
    ],
    "Machinery": [
        "Articulation Motors", "Atmospheric Processors", "Building Fabricators", "Crop Harvesters",
        "Emergency Power Cells", "Energy Grid Assembly", "Exhaust Manifold", "Geological Equipment",
        "Heatsink Interlink", "HN Shock Mount", "Magnetic Emitter Coil", "Marine Equipment",
        "Microbial Furnaces", "Mineral Extractors", "Modular Terminals", "Power Converter",
        "Power Generators", "Power Transfer Bus", "Radiation Baffle", "Reinforced Mounting Plate",
        "Skimmer Components", "Thermal Cooling Units", "Water Purifiers"
    ],
    "Medicines": [
        "Advanced Medicines", "Agri-Medicines", "Basic Medicines", "Combat Stabilisers",
        "Performance Enhancers", "Progenitor Cells"
    ],
    "Metals": [
        "Aluminium", "Beryllium", "Bismuth", "Cobalt", "Copper", "Gallium", "Gold", "Hafnium 178",
        "Indium", "Lanthanum", "Lithium", "Osmium", "Palladium", "Platinum", "Platinum Alloy",
        "Praseodymium", "Samarium", "Silver", "Steel", "Tantalum", "Thallium", "Thorium",
        "Titanium", "Uranium"
    ],
    "Minerals": [
        "Alexandrite", "Bauxite", "Benitoite", "Bertrandite", "Bromellite", "Coltan", "Cryolite",
        "Gallite", "Goslarite", "Grandidierite", "Indite", "Jadeite", "Lepidolite", "Lithium Hydroxide",
        "Low Temperature Diamonds", "Methane Clathrate", "Methanol Monohydrate Crystals", "Moissanite",
        "Monazite", "Musgravite", "Painite", "Pyrophyllite", "Rhodplumsite", "Rutile", "Serendibite",
        "Taaffeite", "Uraninite", "Void Opals"
    ],
    "Salvage": [
        "AI Relics", "Ancient Artefact", "Ancient Key", "Anomaly Particles", "Antimatter Containment Unit",
        "Antique Jewellery", "Antiquities", "Assault Plans", "Black Box", "Commercial Samples",
        "Damaged Escape Pod", "Data Core", "Diplomatic Bag", "Earth Relics", "Encrypted Correspondence",
        "Encrypted Data Storage", "Experimental Chemicals", "Fossil Remnants", "Gene Bank",
        "Geological Samples", "Guardian Casket", "Guardian Orb", "Guardian Relic", "Guardian Tablet",
        "Guardian Totem", "Guardian Urn", "Hostage", "Large Survey Data Cache", "Military Intelligence",
        "Military Plans", "Mollusc Brain Tissue", "Mollusc Fluid", "Mollusc Membrane", "Mollusc Mycelium",
        "Mollusc Soft Tissue", "Mollusc Spores", "Mysterious Idol", "Occupied Escape Pod", "Personal Effects",
        "Pod Core Tissue", "Pod Dead Tissue", "Pod Mesoglea", "Pod Outer Tissue", "Pod Shell Tissue",
        "Pod Surface Tissue", "Pod Tissue", "Political Prisoner", "Precious Gems",
        "Prohibited Research Materials", "Prototype Tech", "Rare Artwork", "Rebel Transmissions",
        "SAP 8 Core Container", "Scientific Research", "Scientific Samples", "Small Survey Data Cache",
        "Space Pioneer Relics", "Tactical Data", "Technical Blueprints", "Thargoid Basilisk Tissue Sample",
        "Thargoid Biological Matter", "Thargoid Bio-Storage Capsule", "Thargoid Cyclops Tissue Sample",
        "Thargoid Glaive Tissue Sample", "Thargoid Heart", "Thargoid Hydra Tissue Sample", "Thargoid Link",
        "Thargoid Orthrus Tissue Sample", "Thargoid Probe", "Thargoid Resin", "Thargoid Sensor",
        "Thargoid Medusa Tissue Sample", "Thargoid Scout Tissue Sample", "Thargoid Technology Samples",
        "Time Capsule", "Titan Deep Tissue Sample", "Titan Maw Deep Tissue Sample",
        "Titan Maw Partial Tissue Sample", "Titan Maw Tissue Sample", "Titan Partial Tissue Sample",
        "Titan Tissue Sample", "Trade Data", "Trinkets of Hidden Fortune", "Unclassified Relic",
        "Unoccupied Escape Pod", "Unstable Data Core", "Wreckage Components"
    ],
    "Slavery": [
        "Imperial Slaves", "Slaves"
    ],
    "Technology": [
        "Advanced Catalysers", "Animal Monitors", "Aquaponic Systems", "Auto Fabricators",
        "Bioreducing Lichen", "Computer Components", "H.E. Suits", "Hardware Diagnostic Sensor",
        "Ion Distributor", "Land Enrichment Systems", "Medical Diagnostic Equipment", "Micro Controllers",
        "Muon Imager", "Nanobreakers", "Resonating Separators", "Robotics", "Structural Regulators",
        "Telemetry Suite"
    ],
    "Textiles": [
        "Conductive Fabrics", "Leather", "Military Grade Fabrics", "Natural Fabrics", "Synthetic Fabrics"
    ],
    "Waste": [
        "Biowaste", "Chemical Waste", "Scrap", "Toxic Waste"
    ],
    "Weapons": [
        "Battle Weapons", "Landmines", "Non-Lethal Weapons", "Personal Weapons", "Reactive Armour"
    ]
}


def sorted_commodities() -> list[str]:
    """ Gets a sorted list of all commodities. """
    result = []
    for val in commodities.values():
        result = result + val
    result.sort()
    return result
