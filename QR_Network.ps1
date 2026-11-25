param([int]$Port=8765, [switch]$Remove)
$ErrorActionPreference='Stop'
$admin=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if(-not $admin){throw 'Run PowerShell as administrator.'}
if($Port -lt 1 -or $Port -gt 65535){throw 'Invalid TCP port.'}
$names=@('QR Mobile LAN TCP','QR Mobile LAN UDP','QR Mobile mDNS')
foreach($name in $names){Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue | Remove-NetFirewallRule}
if(-not $Remove){
  New-NetFirewallRule -DisplayName $names[0] -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -RemoteAddress LocalSubnet -Profile Private,Public | Out-Null
  New-NetFirewallRule -DisplayName $names[1] -Direction Inbound -Action Allow -Protocol UDP -LocalPort 8764 -RemoteAddress LocalSubnet -Profile Private,Public | Out-Null
  New-NetFirewallRule -DisplayName $names[2] -Direction Inbound -Action Allow -Protocol UDP -LocalPort 5353 -RemoteAddress LocalSubnet -Profile Private,Public | Out-Null
  Write-Host "QR LAN rules added: TCP $Port, UDP 8764 and mDNS 5353. Only use trusted local networks."
}else{Write-Host 'QR LAN rules removed.'}
Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -ne '127.0.0.1'} | Format-Table InterfaceAlias,IPAddress,PrefixLength
