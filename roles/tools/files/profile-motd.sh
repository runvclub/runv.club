# the login banner, once per interactive login. touch ~/.hushlogin to skip it
case $- in
    *i*) [ -e "$HOME/.hushlogin" ] || /usr/local/bin/motd ;;
esac
