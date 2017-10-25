-- Lua lighting 
-- variable lighting according to lux values, included is also a video mode and a night mode


commandArray = {}
if devicechanged['Sensor Iemand Thuis'] or devicechanged['Night Mode'] or devicechanged['Lux Living'] or devicechanged['Licht Auto Mode'] then


-- Importing Switches from domoticz
local jsonserver = "http://cookiemonsters.pw:8091"  -- http://<username:password@>domoticz-ip<:port>
local SomeoneHome = (otherdevices['Sensor Iemand Thuis']) --dummy switch to see if someone is home
local NightMode = (otherdevices['Night Mode']) --dummy switch that checks if the house is in nightmode
local AutoMode = (otherdevices['Licht Auto Mode']) --dummy switch to check lights are in auto mode
local KodiMode = (otherdevices['Kodi Ntpc']) -- check if kodi is playing (switch will show 'Video' then)
local LuxCurr = tonumber(otherdevices['Lux Living']) -- read out current lux value from luxmeter

local Lights = {otherdevices_idx['Licht Living'],otherdevices_idx['Licht Bar']} --lights u want to control, in a list seperated by ","
local LightLevel = tonumber(otherdevices_svalues['Licht Living']) -- readout 1 of the controlled lights percentage to get a reference value

local LuxMin = 10 -- Lux Range on which to act ( min = max lights, max = lights will go off above)
local LuxMax = 80

--Values to set Lights to (with rflink+ milight mileage varies best works between 20% - 84% on my rflink) 
local LightMin = 0  -- minimum light percentage
local LightMax = 100 -- maximum light percentage
local LightKodi = 35 -- preferred kodi lightlevel
local LightTarget = 0 -- starting value, needs to be defined @ ZERO! else we're gonna spew errors in some situations.

local Hyst = 2 -- hystereses value, so it doesnt change lights for minimal differences

function powerswitch(Target)
    for i,eachidx in ipairs(Lights) do
        print('switching lights off for '..eachidx)
        os.execute('curl "'..jsonserver..'/json.htm?type=command&dparam=switchlight&idx='..eachidx..'&switchcmd=Off"')
        os.execute('sleep 0.3') --short wait, so lights accept all commands with rflink, can be dropped with ibox i think
    end
end

function setlights(Target)
    for i,eachidx in ipairs(Lights) do
        print('setting lightlevel to '..Target..' for '..eachidx)
        os.execute('curl "'..jsonserver..'/json.htm?type=command&dparam=setcolbrightnessvalue&idx='..eachidx..'&hue=254&brightness='..Target..'&iswhite=true"')
        os.execute('sleep 0.3') --short wait, so lights accept all commands with rflink, can be dropped with ibox 
    end
end

if SomeoneHome=='On' and NightMode=='Off' and AutoMode=='On' then  --lets start calculating some lightstrength
    
    if LuxCurr>LuxMax then  --too bright for lights`
        LightTarget=0
    
    elseif LuxCurr<=LuxMax and KodiMode=="Video" then   --kodi is playing a movie, set kodimode
        LightTarget=LightKodi
    
    elseif LuxCurr<=LuxMin then  --below luxmin, just set max value
        LightTarget=LightMax
    
    else     --LightLevel percentage Calculation, with rounding off
        LightTarget = math.floor((((1-(LuxCurr/(LuxMax-LuxMin)))*(LightMax-LightMin))+LightMin)+0.5)
        print('calculated target is: '..LightTarget)   
        print('Current Lux Value is:'.. LuxCurr) 
    end

elseif SomeoneHome=='Off' or NightMode== 'On' then  --noone home or night mode set target 0 
    LightTarget=0
    
else    --this is only possible on auto mode being Off
    return commandArray
end 

if LightTarget~=LightLevel then -- check if we should change current lightinglevel
    if LightTarget~=0 then
        if LightTarget<=LightLevel-Hyst or LightTarget>=LightLevel+Hyst then -- range check
            setlights(LightTarget)
            
        else
            print('Lights: within hysteresis')
        end
        
    else
        powerswitch(LightTarget) --switching lights Off
    end
    
else    
    print("Lights: no change")
end

end


return commandArray
