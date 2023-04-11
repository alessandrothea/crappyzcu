
det=3
crate=3

for slot in $(seq 1 5); do
    for link in 0 1; do
        wib=${crate}0${slot}
        crappybutler-2g.py np04-wib-$wib enable -l ${link} --dis
    done
done

for slot in 1 2 3 4 5; do
    for link in 0 1; do
        wib=${crate}0${slot}
        crappybutler-2g.py np04-wib-${wib} enable -l $link --dis 
        crappybutler-2g.py np04-wib-${wib} udp-config -l $link np04-wib-${wib}-d${link} np02-srv-001-100G
        crappybutler-2g.py np04-wib-${wib} mux-config -l $link ${det} ${crate} $slot
        #crappybutler-2g.py np04-wib-${wib} fakesrc-config -l $link -n 4
        crappybutler-2g.py np04-wib-${wib} enable -l $link --en
        crappybutler-2g.py np04-wib-${wib} stats -l $link
    done
done