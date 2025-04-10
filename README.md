This is a mod from the Winwifi Python package.

Used primary to scan networks ( this code does many things) 

this mod adds:

- PDf generation after a scan.
- DATABASE generation and update after each scan
- Database of open networks after each scan
- Flask app to show some graphs (for the guys in suits)

All credits go to [https://github.com/mrjohannchang/winwifi].


usage:

''' python -m main.py scan '''

If you copy and paste on winwifi folder (C:\Users\%user%\AppData\Roaming\Python\Python312\site-packages\winwifi)

you can run 

''' python -m winwifi scan'''

''' python app.py ''' 

will start the flask app.

You can mess with the DB on the view.py (SQL is a dark art)
