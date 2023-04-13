for slot in 1 3 5; do
    for link in 0 1; do
        echo "Disabling slot $slot link $link"
        crappybutler.py np04-wib-50${slot} enable -l ${link} --dis
    done
done

for slot in 1 3 5; do
    for link in 0 1; do
        echo "slot $slot link $link"
        crappybutler.py np04-wib-50${slot} enable -l ${link} --dis 
        crappybutler.py np04-wib-50${slot} udp-config -l ${link} np04-wib-50${slot}-d${link} np02-srv-001-100G
        crappybutler.py np04-wib-50${slot} mux-config -l ${link} 1 5 $slot
        crappybutler.py np04-wib-50${slot} fakesrc-config -l ${link} -n 4
        # crappybutler.py np04-wib-50${slot} fakesrc-config -l ${link} -n 0
        crappybutler.py np04-wib-50${slot} enable -l ${link} --en 
        crappybutler.py np04-wib-50${slot} stats -l ${link}
        
    done
done