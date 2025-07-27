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
FlagsAverageAltitude = 1 << 29   # Altitude from Average radius. On when altimeter shows OC/DRP, Off if altimeter is not shown or showing 2Km/SURF.
FlagsFsdJump = 1 << 30           # While jumping to super-cruise or system jump. See also Flags2FsdHyperdriveCharging.
FlagsSrvHighBeam = 1 << 31

# Status.json / Dashboard Flags2 constants
Flags2OnFoot = 1 << 0
Flags2InTaxi = 1 << 1  # (or dropship/shuttle)
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
Flags2Future21 = 1 << 21
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
    'mamba':                        'Mamba',
    'mandalay':                     'Mandalay',
    'orca':                         'Orca',
    'panthermkii':                  'Panther Clipper Mk II',
    'python':                       'Python',
    'python_nx':                    'Python Mk II',
    'scout':                        'Taipan Fighter',
    'sidewinder':                   'Sidewinder',
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
    'mamba':                         'M',
    'mandalay':                      'M',
    'orca':                          'L',
    'panthermkii':                   'L',
    'python':                        'M',
    'python_nx':                     'M',
    'scout':                         '',
    'sidewinder':                    'S',
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
    'adder':                        {'PitchRate': 30.0,  'RollRate': 90.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'anaconda':                     {'PitchRate': 14.0,  'RollRate': 40.0,  'YawRate': 6.0,   'SunPitchUp+Time': 0.0},
    'asp':                          {'PitchRate': 30.0,  'RollRate': 90.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'asp_scout':                    {'PitchRate': 36.0,  'RollRate': 120.0, 'YawRate': 15.0,  'SunPitchUp+Time': 0.0},
    'belugaliner':                  {'PitchRate': 19.0,  'RollRate': 60.0,  'YawRate': 17.0,  'SunPitchUp+Time': 0.0},
    'cobramkiii':                   {'PitchRate': 36.0,  'RollRate': 90.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'cobramkiv':                    {'PitchRate': 24.0,  'RollRate': 90.0,  'YawRate': 10.0,  'SunPitchUp+Time': 0.0},
    'cobramkv':                     {'PitchRate': 37.0,  'RollRate': 110.0, 'YawRate': 22.0,  'SunPitchUp+Time': -0.25},
    'corsair':                      {'PitchRate': 21.0,  'RollRate': 80.0,  'YawRate': 10.0,  'SunPitchUp+Time': 0.0},
    'cutter':                       {'PitchRate': 14.0,  'RollRate': 45.0,  'YawRate': 8.0,   'SunPitchUp+Time': 1.0},
    'diamondback':                  {'PitchRate': 36.0,  'RollRate': 90.0,  'YawRate': 15.0,  'SunPitchUp+Time': 0.0},
    'diamondbackxl':                {'PitchRate': 26.0,  'RollRate': 90.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'dolphin':                      {'PitchRate': 28.0,  'RollRate': 90.0,  'YawRate': 19.0,  'SunPitchUp+Time': 0.0},
    'eagle':                        {'PitchRate': 33.0,  'RollRate': 120.0, 'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'empire_courier':               {'PitchRate': 30.0,  'RollRate': 90.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'empire_eagle':                 {'PitchRate': 30.0,  'RollRate': 90.0,  'YawRate': 15.0,  'SunPitchUp+Time': 0.0},
    'empire_trader':                {'PitchRate': 28.0,  'RollRate': 72.0,  'YawRate': 18.0,  'SunPitchUp+Time': 0.0},
    'federation_corvette':          {'PitchRate': 21.0,  'RollRate': 72.0,  'YawRate': 8.0,   'SunPitchUp+Time': 0.0},
    'federation_dropship':          {'PitchRate': 20.0,  'RollRate': 72.0,  'YawRate': 14.0,  'SunPitchUp+Time': 0.0},
    'federation_dropship_mkii':     {'PitchRate': 30.0,  'RollRate': 90.0,  'YawRate': 18.0,  'SunPitchUp+Time': 0.0},
    'federation_gunship':           {'PitchRate': 19.0,  'RollRate': 60.0,  'YawRate': 18.0,  'SunPitchUp+Time': 0.0},
    'ferdelance':                   {'PitchRate': 20.0,  'RollRate': 72.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'hauler':                       {'PitchRate': 33.0,  'RollRate': 90.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'independant_trader':           {'PitchRate': 26.0,  'RollRate': 90.0,  'YawRate': 11.0,  'SunPitchUp+Time': 0.0},
    'krait_mkii':                   {'PitchRate': 23.0,  'RollRate': 90.0,  'YawRate': 10.0,  'SunPitchUp+Time': 0.0},
    'krait_light':                  {'PitchRate': 23.0,  'RollRate': 90.0,  'YawRate': 10.0,  'SunPitchUp+Time': 0.0},
    'mamba':                        {'PitchRate': 20.0,  'RollRate': 72.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'mandalay':                     {'PitchRate': 40.0,  'RollRate': 120.0, 'YawRate': 24.0,  'SunPitchUp+Time': -1.0},
    'orca':                         {'PitchRate': 20.0,  'RollRate': 60.0,  'YawRate': 18.0,  'SunPitchUp+Time': 0.0},
    'panthermkii':                  {'PitchRate': 16.0,  'RollRate': 25.0,  'YawRate': 10.0,  'SunPitchUp+Time': 1.0},
    'python':                       {'PitchRate': 23.0,  'RollRate': 90.0,  'YawRate': 10.0,  'SunPitchUp+Time': 0.0},
    'python_nx':                    {'PitchRate': 22.0,  'RollRate': 90.0,  'YawRate': 10.0,  'SunPitchUp+Time': 0.0},
    'sidewinder':                   {'PitchRate': 40.0,  'RollRate': 120.0, 'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'type6':                        {'PitchRate': 26.0,  'RollRate': 90.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'type7':                        {'PitchRate': 17.0,  'RollRate': 60.0,  'YawRate': 18.0,  'SunPitchUp+Time': 0.0},
    'type8':                        {'PitchRate': 16.0,  'RollRate': 60.0,  'YawRate': 9.0,   'SunPitchUp+Time': 0.0},
    'type9':                        {'PitchRate': 12.0,  'RollRate': 18.0,  'YawRate': 6.0,   'SunPitchUp+Time': 1.0},
    'type9_military':               {'PitchRate': 12.0,  'RollRate': 17.0,  'YawRate': 5.0,   'SunPitchUp+Time': 0.0},
    'typex':                        {'PitchRate': 20.0,  'RollRate': 72.0,  'YawRate': 14.0,  'SunPitchUp+Time': 0.0},
    'typex_2':                      {'PitchRate': 20.0,  'RollRate': 72.0,  'YawRate': 13.0,  'SunPitchUp+Time': 0.0},
    'typex_3':                      {'PitchRate': 20.0,  'RollRate': 72.0,  'YawRate': 14.0,  'SunPitchUp+Time': 0.0},
    'viper':                        {'PitchRate': 30.0,  'RollRate': 90.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'viper_mkiv':                   {'PitchRate': 26.0,  'RollRate': 90.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0},
    'vulture':                      {'PitchRate': 33.0,  'RollRate': 90.0,  'YawRate': 12.0,  'SunPitchUp+Time': 0.0}
}

# Ship default RPY rates in deg/sec at 100% Supercruise throttle
# Default data comes from 'marx': https://forums.frontier.co.uk/threads/supercruise-handling-of-ships.396845/
ship_rpy_sc_100 = {
    'adder':                         {'PitchRate': 23.0,  'RollRate': 90.0,  'YawRate': 8.0,  'SunPitchUp+Time': 0.0},
    'anaconda':                      {'PitchRate': 9.0,   'RollRate': 36.0,  'YawRate': 3.0,  'SunPitchUp+Time': 0.0},
    'asp':                           {'PitchRate': 23.0,  'RollRate': 72.0,  'YawRate': 5.0,  'SunPitchUp+Time': 0.0},
    'asp_scout':                     {'PitchRate': 28.0,  'RollRate': 90.0,  'YawRate': 10.0, 'SunPitchUp+Time': 0.0},
    'belugaliner':                   {'PitchRate': 13.0,  'RollRate': 45.0,  'YawRate': 15.0, 'SunPitchUp+Time': 0.0},
    'cobramkiii':                    {'PitchRate': 26.0,  'RollRate': 72.0,  'YawRate': 5.0,  'SunPitchUp+Time': 0.0},
    'cobramkiv':                     {'PitchRate': 16.0,  'RollRate': 90.0,  'YawRate': 7.0,  'SunPitchUp+Time': 0.0},
    'cobramkv':                      {'PitchRate': 37.0,  'RollRate': 110.0, 'YawRate': 22.0, 'SunPitchUp+Time': -0.25},
    'corsair':                       {'PitchRate': 21.0,  'RollRate': 80.0,  'YawRate': 10.0, 'SunPitchUp+Time': 0.0},
    'cutter':                        {'PitchRate': 9.0,   'RollRate': 40.0,  'YawRate': 5.0,  'SunPitchUp+Time': 1.0},
    'diamondback':                   {'PitchRate': 23.0,  'RollRate': 90.0,  'YawRate': 9.0,  'SunPitchUp+Time': 0.0},
    'diamondbackxl':                 {'PitchRate': 20.0,  'RollRate': 72.0,  'YawRate': 8.0,  'SunPitchUp+Time': 0.0},
    'dolphin':                       {'PitchRate': 19.0,  'RollRate': 72.0,  'YawRate': 13.0, 'SunPitchUp+Time': 0.0},
    'eagle':                         {'PitchRate': 24.0,  'RollRate': 90.0,  'YawRate': 8.0,  'SunPitchUp+Time': 0.0},
    'empire_courier':                {'PitchRate': 24.0,  'RollRate': 90.0,  'YawRate': 8.0,  'SunPitchUp+Time': 0.0},
    'empire_eagle':                  {'PitchRate': 23.0,  'RollRate': 72.0,  'YawRate': 9.0,  'SunPitchUp+Time': 0.0},
    'empire_trader':                 {'PitchRate': 21.0,  'RollRate': 72.0,  'YawRate': 12.0, 'SunPitchUp+Time': 0.0},
    'federation_corvette':           {'PitchRate': 13.0,  'RollRate': 60.0,  'YawRate': 5.0,  'SunPitchUp+Time': 0.0},
    'federation_dropship':           {'PitchRate': 12.0,  'RollRate': 72.0,  'YawRate': 9.0,  'SunPitchUp+Time': 0.0},
    'federation_dropship_mkii':      {'PitchRate': 21.0,  'RollRate': 72.0,  'YawRate': 12.0, 'SunPitchUp+Time': 0.0},
    'federation_gunship':            {'PitchRate': 12.0,  'RollRate': 72.0,  'YawRate': 11.0, 'SunPitchUp+Time': 0.0},
    'ferdelance':                    {'PitchRate': 12.0,  'RollRate': 60.0,  'YawRate': 8.0,  'SunPitchUp+Time': 0.0},
    'hauler':                        {'PitchRate': 23.0,  'RollRate': 90.0,  'YawRate': 8.0,  'SunPitchUp+Time': 0.0},
    'independant_trader':            {'PitchRate': 16.0,  'RollRate': 90.0,  'YawRate': 7.0,  'SunPitchUp+Time': 0.0},
    'krait_mkii':                    {'PitchRate': 13.0,  'RollRate': 72.0,  'YawRate': 6.0,  'SunPitchUp+Time': 0.0},
    'krait_light':                   {'PitchRate': 14.0,  'RollRate': 72.0,  'YawRate': 6.0,  'SunPitchUp+Time': 0.0},
    'mamba':                         {'PitchRate': 13.0,  'RollRate': 72.0,  'YawRate': 8.0,  'SunPitchUp+Time': 0.0},
    'mandalay':                      {'PitchRate': 24.0,  'RollRate': 90.0,  'YawRate': 16.0, 'SunPitchUp+Time': -1.0},
    'orca':                          {'PitchRate': 14.0,  'RollRate': 51.0,  'YawRate': 12.0, 'SunPitchUp+Time': 0.0},
    'panthermkii':                   {'PitchRate': 9.7,   'RollRate': 20.0,  'YawRate': 6.0,  'SunPitchUp+Time': 1.0},
    'python':                        {'PitchRate': 14.0,  'RollRate': 72.0,  'YawRate': 6.0,  'SunPitchUp+Time': 0.0},
    'python_nx':                     {'PitchRate': 22.0,  'RollRate': 90.0,  'YawRate': 10.0, 'SunPitchUp+Time': 0.0},
    'sidewinder':                    {'PitchRate': 28.0,  'RollRate': 90.0,  'YawRate': 8.0,  'SunPitchUp+Time': 0.0},
    'type6':                         {'PitchRate': 16.0,  'RollRate': 72.0,  'YawRate': 8.0,  'SunPitchUp+Time': 0.0},
    'type7':                         {'PitchRate': 11.0,  'RollRate': 45.0,  'YawRate': 11.0, 'SunPitchUp+Time': 0.0},
    'type8':                         {'PitchRate': 16.0,  'RollRate': 60.0,  'YawRate': 9.0,  'SunPitchUp+Time': 0.0},
    'type9':                         {'PitchRate': 7.0,   'RollRate': 15.0,  'YawRate': 3.0,  'SunPitchUp+Time': 1.0},
    'type9_military':                {'PitchRate': 8.0,   'RollRate': 15.0,  'YawRate': 4.0,  'SunPitchUp+Time': 0.0},
    'typex':                         {'PitchRate': 13.0,  'RollRate': 60.0,  'YawRate': 9.0,  'SunPitchUp+Time': 0.0},
    'typex_2':                       {'PitchRate': 13.0,  'RollRate': 72.0,  'YawRate': 9.0,  'SunPitchUp+Time': 0.0},
    'typex_3':                       {'PitchRate': 12.0,  'RollRate': 60.0,  'YawRate': 9.0,  'SunPitchUp+Time': 0.0},
    'viper':                         {'PitchRate': 20.0,  'RollRate': 72.0,  'YawRate': 8.0,  'SunPitchUp+Time': 0.0},
    'viper_mkiv':                    {'PitchRate': 16.0,  'RollRate': 72.0,  'YawRate': 8.0,  'SunPitchUp+Time': 0.0},
    'vulture':                       {'PitchRate': 24.0,  'RollRate': 72.0,  'YawRate': 8.0,  'SunPitchUp+Time': 0.0}
}
