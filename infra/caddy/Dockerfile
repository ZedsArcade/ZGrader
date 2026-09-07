# The Caddyfile ships inside the image rather than being mounted from the host.
#
# It used to be a bind mount, which does not work in every deployment: a
# relative mount source is resolved by the Docker *daemon* on the host, and
# under Portainer the compose file lives in Portainer's own storage with no
# checkout beside it -- so the path did not exist, Docker created it as a
# directory, and Caddy refused to start. The workaround was CADDYFILE_PATH
# pointing at a copy on the host, which made the config a second source of
# truth that nothing noticed drifting from this one.
#
# A build context does not have that problem. It is read by the Docker
# *client*, which does have the repository, which is why `build: ./backend`
# has always worked in the same deployment where the mount did not.
FROM caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile

# Fail the build, not the site. A malformed Caddyfile used to take the proxy
# down at container start -- and the proxy is the only way in -- with
# docs/deployment.md asking whoever changed it to remember to validate first.
# Here the image simply does not build, so a broken config cannot deploy and
# the check cannot be forgotten.
RUN caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
