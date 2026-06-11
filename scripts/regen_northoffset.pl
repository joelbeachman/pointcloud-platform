#!/usr/bin/env perl
# regen_northoffset.pl — Regenerate metadata.json with quaternion-derived northOffset.
#
# The stored rotZ_deg is ambiguous near gimbal lock (rotX≈±180° or rotY≈±180°).
# We derive northOffset directly from the quaternion as the compass bearing of
# the camera's local X-axis in the LV95 world frame:
#   northOffset = atan2(1 - 2*(qy²+qz²), 2*(qx*qy + qw*qz))  [radians → degrees]
#
# This is the panorama-center bearing that Pannellum's northOffset parameter expects,
# and allows a clean  yaw = bearing - northOffset  formula (no ±90 correction).
#
# Reads:  data/eggiswil_backup/image_poses.csv          (camera quaternions per image)
# Writes: data/panoramas/haus-eggiwil/metadata.json      (in place — back it up first)
#
# Usage: perl scripts/regen_northoffset.pl
# Note: paths are hardcoded relative to the repo root, so run it from there.

use strict;
use warnings;
use POSIX qw(atan2);

my $CSV_PATH  = 'data/eggiswil_backup/image_poses.csv';
my $META_IN   = 'data/panoramas/haus-eggiwil/metadata.json';
my $META_OUT  = $META_IN;   # overwrite in place

# ── 1. Read quaternions from CSV ────────────────────────────────────────────
open my $fh, '<', $CSV_PATH or die "Cannot open $CSV_PATH: $!";
my $header = <$fh>;
chomp $header;
my @cols = split /,/, $header;

# Map column name → 0-based index so we can address fields by name below.
my %ci;
for my $i (0..$#cols) {
    (my $name = $cols[$i]) =~ s/"//g;
    $ci{$name} = $i;
}
die "Missing column" unless exists $ci{qw} && exists $ci{qx} && exists $ci{qy} && exists $ci{qz} && exists $ci{file};

my %north_by_file;  # file → northOffset in degrees

while (my $line = <$fh>) {
    chomp $line;
    # simple CSV split (no embedded commas in these fields)
    my @f = split /,/, $line;
    my $file = $f[ $ci{file} ];
    $file =~ s/"//g;

    my $qw = $f[ $ci{qw} ] + 0;
    my $qx = $f[ $ci{qx} ] + 0;
    my $qy = $f[ $ci{qy} ] + 0;
    my $qz = $f[ $ci{qz} ] + 0;

    # X-axis of camera in LV95 world frame (first column of rotation matrix)
    my $Rx = 1.0 - 2.0*($qy*$qy + $qz*$qz);
    my $Ry = 2.0*($qx*$qy + $qw*$qz);

    # Compass bearing of that axis (atan2(East, North))
    my $north_offset = atan2($Rx, $Ry) * (180.0 / 3.14159265358979);

    $north_by_file{$file} = sprintf("%.2f", $north_offset);
}
close $fh;

# ── 2. Patch metadata.json ──────────────────────────────────────────────────
open my $mfh, '<', $META_IN or die "Cannot open $META_IN: $!";
my $json = do { local $/; <$mfh> };
close $mfh;

# First substitution pass (legacy): rewrites northOffset for entries whose keys
# appear in the exact order  "path", ... "x" ... "northOffset".  Superseded by
# the more tolerant patch_metadata() below, which is applied afterwards and
# produces the same final values; kept to preserve existing behavior.
my $updated = 0;
$json =~ s|"path"\s*:\s*"/data/panoramas/haus-eggiwil/([^"]+)"\s*,\s*"x"[^}]+"northOffset"\s*:\s*[-\d.]+|
    my $file = $1;
    if (exists $north_by_file{$file}) {
        $updated++;
        $& =~ s/"northOffset"\s*:\s*[-\d.]+/"northOffset":$north_by_file{$file}/r;
    } else {
        $&;
    }
|ge;

# Second pass: simpler targeted replacement — patch each northOffset that
# follows a matching "path" entry, regardless of intermediate keys.
$json = patch_metadata($json, \%north_by_file);

open my $out, '>', $META_OUT or die "Cannot write $META_OUT: $!";
print $out $json;
close $out;

print "Done. Updated northOffset values using quaternion formula.\n";
print "Verify a few:\n";
# Intended to print only the first 6 entries, but `my $n` is re-declared (and
# so reset) on every iteration, so in practice all entries are printed.
# Left untouched to keep the script's output identical.
for my $f (sort { $a cmp $b } keys %north_by_file) {
    printf "  %-45s  northOffset = %s\n", $f, $north_by_file{$f};
    last if ++my $n >= 6;
}

sub patch_metadata {
    my ($json, $map) = @_;
    # Match each panorama object and update its northOffset
    $json =~ s{
        ("path"\s*:\s*"/data/panoramas/haus-eggiwil/)([^"]+)(")
        (.*?)
        ("northOffset"\s*:\s*)([-\d.]+)
    }{
        my $file  = $2;
        my $repl  = exists $map->{$file} ? $map->{$file} : $6;
        $1.$2.$3.$4.$5.$repl
    }gexs;
    return $json;
}
