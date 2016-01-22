from flask import Flask, redirect, render_template, request
import random, sqlite3, os, validators, time
app = Flask(__name__)

'''
This application has the following dependencies:
    - Flask
    - validators
'''

#Application Variables

APP_URL = "127.0.0.1:5000"
FILENAME = 'database.sqlite3'
WORKING_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

database_connection = None

#Helper Methods

def generate_random_code(length: int) -> str:
    '''
    Generates a n-digit random code of alphanumeric digits
    :param length: Length of the desired code
    :return: The random code.
    '''
    charset="abcdefghjkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789" #valid characters for short-codes, excludes ones that look to similar (i.e. 1,l,i, 0,O etc.)
    return "".join([charset[random.randint(0, len(charset)-1)] for x in range(length)])

def format_url(url: str) -> str:
    '''
    Attempts to create a well-formed URL
    :param url: string of the URL to validate
    :return: a valid URL, or -1 if the URL could not be formatted
    '''
    if validators.url(url):
        return url
    elif validators.domain(url):
        if validators.url("http://" + url):
            return "http://" + url

    return -1

#Application Classes

class Link():
    def __init__(self, short_link: str, url: str, deletion_id: str, clicks: int, timestamp: int):
        self.url = url
        self.short_link = short_link
        self.deletion_id = deletion_id
        self.clicks = clicks
        self.timestamp = timestamp

    def __repr__(self):
        return "[URL: {0}, SL: {1}, Deletion ID = {2}, Clicks = {3}, Timestamp = {4}]".format(self.url, self.short_link, self.deletion_id, self.clicks, self.timestamp)

class LinkDatabase():
    def __init__(self, filename: str):
        """
        Initializes a new instance of the LinkDatabase class, which provides a layer of interaction between the
        application and sqlite
        :param filename: A string containing the name of the database file, stored within the same directory as LinkShortener.py
        :return: None
        """
        db_path = os.path.join(WORKING_DIRECTORY, filename)

        self._connection = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self._connection.cursor()

    def close(self, commit_changes: bool = True):
        """
        Closes the current database connection.
        :param commit_changes: Default true; whether or not to write changes to the database before exit
        :return: None
        """
        self.cursor.close()
        if commit_changes:
            self._connection.commit()
        self._connection.close()

    def get_link_from_short(self, short_link: str):
        """
        Returns a link based on a given short link code
        :param short_link: Short link code
        :return: A Link object representing the row in the database
        """
        self.cursor.execute("""
            select * from links
            where short_link = ?
            """, (short_link,))

        result = self.cursor.fetchone()
        if not result == None:
            return Link(short_link=result[0], url=result[1], deletion_id=result[2], clicks=result[3], timestamp=result[4])
        else:
            return None

    def update_link(self, link: Link):
        self.cursor.execute("""
            update links
            set url=?,deletion_id=?,clicks=?,timestamp=?
            where short_link = ?
            """,(link.url, link.deletion_id, link.clicks, link.timestamp, link.short_link))
        self._connection.commit()


    def delete_link(self, link: Link):
        self.cursor.execute("delete from links where short_link = ?",(link.short_link,))
        self._connection.commit()

    def add_link(self, link: Link):
        self.cursor.execute("""
            insert into links (url, short_link, deletion_id, clicks, timestamp)
            VALUES (?,?,?,?,?)
            """,(link.url, link.short_link, link.deletion_id, link.clicks, link.timestamp))
        self._connection.commit()

    def get_valid_short_link(self, length: int) -> str:
        charset="abcdefghjkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"

        while True:
            candidate = generate_random_code(length)
            if not self.is_shortcode_in_db(candidate):
                return candidate


    def is_shortcode_in_db(self, shortCode: str) -> bool:
        return self.cursor.execute("select count(short_link) from links where short_link=?",(shortCode,)).fetchone()[0] > 0

    @staticmethod
    def create_database(filename: str):
        """
        Creates a new empty database.
        :param filename: What filename we want the database to be called.
        :return: None
        """

        db_path = os.path.join(WORKING_DIRECTORY, filename)

        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        cursor.execute("""
            create table "links" (
            `short_link`	text unique,
            `url`	text,
            `deletion_id`	text unique,
            `clicks`	integer default 0,
            `timestamp`	integer,
            primary key(short_link)    --primary key to success
        )""")

        connection.commit()
        connection.close()

@app.route('/')
def main_page():
    return render_template('main_page.html', app_url = APP_URL)

@app.route('/', methods=['POST'])
def handle_new_url():
    submitted_url = request.form["url_submit_field"].strip()
    formatted_url = format_url(submitted_url)
    if formatted_url == -1:
        return render_template('response_page.html', app_url= APP_URL, response_line_1="The request could not be processed for the following reason:", response_line_2="The specified URL ({0}) is invalid.".format(submitted_url))

    short_code = database_connection.get_valid_short_link(length=3)
    deletion_id = generate_random_code(6)
    current_epoch_time = int(time.time())

    new_link = Link(short_code,formatted_url,deletion_id,0,current_epoch_time)

    database_connection.add_link(new_link)

    return render_template('new_url_page.html', app_url = APP_URL, short_code = short_code, deletion_code=deletion_id)

@app.route('/<argument>')
@app.route('/<argument>/')
def handle_redirect_url(argument=None):
    if not argument is None:
        link_object = database_connection.get_link_from_short(argument)
        if link_object is None:
            return render_template('response_page.html', app_url= APP_URL, response_line_1="The request could not be processed for the following reason:", response_line_2="The specified short code does not exist.")

        print(link_object)
        link_object.clicks += 1
        database_connection.update_link(link_object)
        return redirect(link_object.url)

@app.route('/<shortcode>/delete')
@app.route('/<shortcode>/delete/')
def deletion_page_request(shortcode=None):
    if not database_connection.is_shortcode_in_db(shortcode):
        return render_template('response_page.html', app_url = APP_URL, response_line_1="The request could not be processed for the following reason:", response_line_2="The specified short URL does not exist")

    return render_template('deletion_page.html', app_url = APP_URL, short_code = shortcode, response_line_1="Enter your deletion code to delete a shortlink:")

@app.route('/<shortcode>/stats')
@app.route('/<shortcode>/stats/')
def get_statistics_page(shortcode=None):
    link_object = database_connection.get_link_from_short(shortcode)

    if link_object == None:
        return render_template('response_page.html', app_url = APP_URL, response_line_1="The request could not be processed for the following reason:", response_line_2="The specified short URL does not exist")

    return render_template('response_page.html', app_url = APP_URL, short_code = shortcode, response_line_1="Statistics:", response_line_2="Time Created: {0}, Clicks: {1}".format(link_object.timestamp, link_object.clicks))

@app.route('/<shortcode>/delete', methods=["POST"])
@app.route('/<shortcode>/delete/', methods=["POST"])
def handle_deletion_request(shortcode=None):
    deletion_code = request.form["deletion_code_field"]
    link_object = database_connection.get_link_from_short(shortcode)

    if link_object == None:
        return "Error processing request: the shortcode could not be found."

    if deletion_code == link_object.deletion_id:
        database_connection.delete_link(link_object)
        return render_template('response_page.html', app_url = APP_URL, response_line_1="The link has been deleted.")
    else:
        return render_template('deletion_page.html', app_url = APP_URL, response_line_1="Unable to carry out request,", response_line_2="the deletion code you entered was not valid.")


if __name__ == '__main__':

    if not os.path.exists(os.path.join(WORKING_DIRECTORY, FILENAME)):
        print("Database not found, creating '{0}' in '{1}'".format(FILENAME, WORKING_DIRECTORY))
        LinkDatabase.create_database(os.path.join(WORKING_DIRECTORY, FILENAME))

    database_connection = LinkDatabase(os.path.join(WORKING_DIRECTORY, FILENAME))

    app.run(debug=True)