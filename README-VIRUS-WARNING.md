# Handling Windows Defender Warnings with EDAPGui

## Why Does Windows Flag the Application?

When you download and run EDAPGui.exe, Windows Defender or other antivirus software may flag it as potentially harmful. This is a **false positive** and happens for these reasons:

1. **PyInstaller-packaged applications** are often flagged because they contain executable code bundled in a specific way
2. **Non-code signed executables** from the internet are treated with extra caution by Windows
3. **Low prevalence software** (applications not widely distributed) trigger heuristic detection

## Steps We've Taken to Reduce False Positives

We've implemented several measures to make the executable as safe as possible:

1. **Version information** - We've added proper version metadata to the executable
2. **Symbol stripping** - Symbols that can trigger antivirus heuristics are removed
3. **Self-signed certificate** - While not as trusted as a commercial certificate, we digitally sign our releases
4. **No admin privileges** - The application doesn't request elevated privileges

## How to Safely Use EDAPGui

### Option 1: Add an Exclusion (Recommended for Regular Users)

1. Right-click the EDAPGui.exe file
2. Select "Properties"
3. At the bottom of the Properties dialog, check "Unblock" if present
4. Click "Apply" and "OK"
5. If Windows still blocks it, you can add an exclusion in Windows Defender:
   - Open Windows Security
   - Go to "Virus & threat protection"
   - Under "Virus & threat protection settings," click "Manage settings"
   - Scroll down to "Exclusions" and click "Add or remove exclusions"
   - Add the EDAPGui.exe file or its containing folder

### Option 2: Run Anyway (One-time Use)

1. When you see the Windows warning, click "More info"
2. Then click "Run anyway"

### Option 3: Check Digital Signature (Most Secure)

1. Right-click the EDAPGui.exe file
2. Select "Properties"
3. Go to the "Digital Signatures" tab
4. Verify that a signature is present
5. Double-click the signature to view certificate details
6. Check that the signature is valid (though it may display "unknown publisher" for self-signed certs)

## Is EDAPGui Safe?

Yes, EDAPGui is safe to use. The source code is open and available for inspection in our GitHub repository. The executable is built using automated processes in GitHub Actions with no human intervention that could introduce malware.

## Long-term Solutions

We are working to address this issue by:

1. Implementing code signing with a trusted certificate from a recognized Certificate Authority
2. Submitting the application to Microsoft for analysis through their [Windows Defender Intelligence portal](https://www.microsoft.com/en-us/wdsi/filesubmission)
3. Building the application with more virus-scanner-friendly options
4. Increasing the application's prevalence which helps reduce false positives over time

If you have any concerns, you can always build the application directly from the source code rather than using the pre-built executable. 